
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import sleep
from uuid import uuid4

from application.execution_lease_heartbeat import (
    ExecutionLeaseLost,
)
from application.research_workflow_service import (
    ResearchWorkflowService,
)
from persistence.database import SessionLocal
from persistence.execution_lease_repository import (
    ExecutionLeaseRepository,
    ExecutionLeaseUnavailable,
)
from persistence.research_session_repository import (
    ResearchSessionRepository,
)


class BlockingGraph:

    def __init__(self):

        self.entered = Event()
        self.release = Event()
        self.calls = 0

    def invoke(self, state, config=None):

        self.calls += 1

        self.entered.set()

        if not self.release.wait(timeout=15):
            raise TimeoutError(
                "Test graph was not released"
            )

        return dict(state)


def make_session():

    with SessionLocal() as db:

        session = ResearchSessionRepository(db).create(
            topic="Workflow heartbeat integration test",
            scope=None,
        )

        return session.id


def delete_session(session_id):

    with SessionLocal() as db:

        record = ResearchSessionRepository(db).get(
            session_id
        )

        if record is not None:

            db.delete(record)
            db.commit()


def get_lease_state(session_id):

    with SessionLocal() as db:

        record = ResearchSessionRepository(db).get(
            session_id
        )

        return (
            record.execution_owner,
            record.execution_lease_expires_at,
            record.execution_lease_version,
        )


def expire_lease(session_id):

    with SessionLocal() as db:

        repository = ResearchSessionRepository(db)

        record = repository.get(
            session_id
        )

        assert record is not None

        record.execution_lease_expires_at = (
            record.execution_lease_expires_at.replace(
                year=2000
            )
        )

        db.commit()


def main():

    print()
    print("WORKFLOW HEARTBEAT INTEGRATION")
    print("==============================")

    session_id = make_session()

    try:

        graph = BlockingGraph()

        service = ResearchWorkflowService(
            graph=graph,
            session_factory=SessionLocal,
            lease_duration_seconds=3,
            heartbeat_interval_seconds=0.5,
        )

        with ThreadPoolExecutor(max_workers=2) as pool:

            future = pool.submit(
                service.resume,
                session_id,
            )

            try:

                assert graph.entered.wait(timeout=10)

                original_owner, original_expiry, original_version = (
                    get_lease_state(session_id)
                )

                assert original_owner is not None

                sleep(5)

                current_owner, current_expiry, current_version = (
                    get_lease_state(session_id)
                )

                assert current_owner == original_owner
                assert current_version == original_version
                assert current_expiry > original_expiry

                print(
                    "TEST 1 - Lease renewed during workflow: PASSED"
                )

                try:

                    service.resume(
                        session_id
                    )

                except ExecutionLeaseUnavailable:

                    pass

                else:

                    raise AssertionError(
                        "Competing execution acquired the lease."
                    )

                assert graph.calls == 1

                print(
                    "TEST 2 - Competing workflow rejected: PASSED"
                )

            finally:

                graph.release.set()

            result = future.result(timeout=10)

        assert result.session_id == session_id

        owner, expiry, version = get_lease_state(
            session_id
        )

        assert owner is None
        assert expiry is None

        print(
            "TEST 3 - Heartbeat stopped and lease released: PASSED"
        )

        with SessionLocal() as db:

            replacement = ExecutionLeaseRepository(db).acquire(
                session_id,
                duration_seconds=3,
            )

            assert replacement.version > version

            assert ExecutionLeaseRepository(db).release(
                replacement
            ) is True

        print(
            "TEST 4 - New execution acquired lease: PASSED"
        )

        failure_graph = BlockingGraph()

        failure_service = ResearchWorkflowService(
            graph=failure_graph,
            session_factory=SessionLocal,
            lease_duration_seconds=3,
            heartbeat_interval_seconds=0.5,
        )

        with ThreadPoolExecutor(max_workers=2) as pool:

            future = pool.submit(
                failure_service.resume,
                session_id,
            )

            try:

                assert failure_graph.entered.wait(timeout=10)

                expire_lease(
                    session_id
                )

                sleep(1.5)

            finally:

                failure_graph.release.set()

            try:

                future.result(timeout=10)

            except ExecutionLeaseLost:

                pass

            else:

                raise AssertionError(
                    "Expected execution lease loss."
                )

        print(
            "TEST 5 - Heartbeat ownership loss detected: PASSED"
        )

        print()
        print("PASS")

    finally:

        delete_session(
            session_id
        )

        print(
            f"Disposable session removed: {session_id}"
        )


if __name__ == "__main__":

    main()
