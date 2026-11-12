from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

from application.research_workflow_service import ResearchWorkflowService
from persistence.database import SessionLocal
from persistence.execution_lease_repository import (
    ExecutionLeaseRepository,
    ExecutionLeaseUnavailable,
)
from persistence.research_session_repository import ResearchSessionRepository


class BlockingGraph:
    def __init__(self, fail=False):
        self.entered = Event()
        self.release = Event()
        self.calls = 0
        self.fail = fail

    def invoke(self, state, config=None):

        self.calls += 1

        self.entered.set()

        if not self.release.wait(timeout=15):
            raise TimeoutError(
                "Test graph was not released"
            )

        if self.fail:
            raise RuntimeError(
                "expected graph failure"
            )

        return dict(state)


class ImmediateGraph:
    def __init__(self):
        self.calls = 0

    def invoke(self, state, config=None):

        self.calls += 1

        return dict(state)


def make_session():
    with SessionLocal() as db:
        return ResearchSessionRepository(db).create(
            topic="Execution lease integration", scope=None
        ).id


def delete_session(session_id):
    with SessionLocal() as db:
        record = ResearchSessionRepository(db).get(session_id)
        if record is not None:
            db.delete(record)
            db.commit()


def check_no_owner(session_id):
    with SessionLocal() as db:
        record = ResearchSessionRepository(db).get(session_id)
        assert record.execution_owner is None
        assert record.execution_lease_expires_at is None


def main():
    print("STAGE 7.21C - WORKFLOW LEASE INTEGRATION")
    print("=========================================")
    session_id = make_session()
    try:
        graph = BlockingGraph()
        service = ResearchWorkflowService(graph, SessionLocal)
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(service.resume, session_id)
            try:
                assert graph.entered.wait(10), "First resume never entered graph"
                try:
                    service.resume(session_id)
                except ExecutionLeaseUnavailable:
                    pass
                else:
                    raise AssertionError("Concurrent resume unexpectedly acquired lease")
                assert graph.calls == 1, "Second resume entered graph"
                print("TEST 1 - Competing resume rejected before graph: PASSED")
            finally:
                graph.release.set()
            result = first.result(timeout=10)
        assert result.session_id == session_id
        check_no_owner(session_id)
        print("TEST 2 - Lease released after normal return: PASSED")

        failure_graph = BlockingGraph(fail=True)
        failure_graph.release.set()
        failure_service = ResearchWorkflowService(failure_graph, SessionLocal)
        try:
            failure_service.resume(session_id)
        except RuntimeError as exc:
            assert str(exc) == "expected graph failure", str(exc)
        else:
            raise AssertionError("Expected graph exception")
        check_no_owner(session_id)
        print("TEST 3 - Lease released after graph exception: PASSED")

        immediate = ImmediateGraph()
        followup = ResearchWorkflowService(immediate, SessionLocal)
        followup.resume(session_id)
        assert immediate.calls == 1
        check_no_owner(session_id)
        print("TEST 4 - Session can resume after release: PASSED")

        # A completed session must not invoke the graph, and must not retain a lease.
        with SessionLocal() as db:
            ResearchSessionRepository(db).set_status(session_id, "completed")
        try:
            followup.resume(session_id)
        except ValueError:
            pass
        else:
            raise AssertionError("Completed session was resumed")
        assert immediate.calls == 1
        check_no_owner(session_id)
        print("TEST 5 - Completed session rejected without graph: PASSED")
        print("\nPASS")
    finally:
        delete_session(session_id)
        print(f"Disposable session removed: {session_id}")


if __name__ == "__main__":
    main()
