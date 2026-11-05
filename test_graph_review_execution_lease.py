
from dataclasses import replace
from uuid import uuid4

from langgraph.graph import (
    StateGraph,
    START,
    END,
)

from domain.review import (
    ResearchQuestionReview,
    ReviewedClaim,
)

from graph.state import ResearchState

from nodes.review_question import (
    ReviewQuestionNode,
)

from persistence.database import SessionLocal

from persistence.execution_lease_repository import (
    ExecutionLeaseFenceRejected,
    ExecutionLeaseRepository,
)

from test_search_result_fencing import (
    create_session,
    delete_session,
    expire_lease,
)

from test_review_selection_fencing import (
    create_review_question,
)

from test_review_persistence_fencing import (
    get_snapshot,
    set_question_status,
)

from test_review_provenance_fencing import (
    create_source_and_findings,
    delete_provenance,
    get_provenance_snapshot,
)


class DeterministicReviewAgent:

    def __init__(self):

        self.calls = 0

    def review(
        self,
        research_question,
        findings_text,
        valid_finding_ids,
    ):

        self.calls += 1

        assert research_question
        assert findings_text
        assert valid_finding_ids

        finding_ids = sorted(
            valid_finding_ids
        )

        return ResearchQuestionReview(
            answer=(
                "The supplied findings support "
                "the test conclusion."
            ),
            reviewed_claims=[
                ReviewedClaim(
                    claim=(
                        "The evidence supports "
                        "the reviewed conclusion."
                    ),
                    supporting_finding_ids=[
                        finding_ids[0],
                    ],
                    contradicting_finding_ids=[],
                    confidence="high",
                ),
            ],
            contradictions=[],
            evidence_gaps=[],
            overall_confidence="high",
            sufficient_evidence=True,
        )


class DeterministicContextBuilder:

    def build(
        self,
        findings,
        sources_by_id,
    ):

        assert findings
        assert sources_by_id

        return "\n".join(
            finding.claim
            for finding in findings
        )


def create_graph(
    review_agent,
):

    builder = StateGraph(
        ResearchState
    )

    builder.add_node(
        "review_question",
        ReviewQuestionNode(
            session_factory=SessionLocal,
            review_agent=review_agent,
            context_builder=(
                DeterministicContextBuilder()
            ),
        ),
    )

    builder.add_edge(
        START,
        "review_question",
    )

    builder.add_edge(
        "review_question",
        END,
    )

    return builder.compile()


def invoke_graph(
    graph,
    session_id,
    question_id,
    lease=None,
):

    configurable = {}

    if lease is not None:

        configurable[
            "execution_lease"
        ] = lease

    return graph.invoke(
        {
            "session_id": session_id,
            "current_review_question_id": (
                question_id
            ),
            "current_review_question": (
                "What does the test evidence establish?"
            ),
        },
        config={
            "configurable": configurable,
        },
    )


def expect_rejection(
    graph,
    session_id,
    question_id,
    lease,
    exception_type,
    protected_question_ids,
):

    before = {
        item: (
            get_snapshot(item),
            get_provenance_snapshot(item),
        )
        for item in protected_question_ids
    }

    try:

        invoke_graph(
            graph,
            session_id,
            question_id,
            lease,
        )

    except exception_type:

        pass

    else:

        raise AssertionError(
            "Graph execution was unexpectedly accepted."
        )

    after = {
        item: (
            get_snapshot(item),
            get_provenance_snapshot(item),
        )
        for item in protected_question_ids
    }

    assert after == before, (
        "Rejected graph execution changed "
        "review persistence."
    )


def main():

    print()
    print("GRAPH REVIEW EXECUTION LEASE")
    print("============================")

    sessions = []

    try:

        session_a = create_session()
        sessions.append(session_a)

        session_b = create_session()
        sessions.append(session_b)

        session_c = create_session()
        sessions.append(session_c)

        question_a = create_review_question(
            session_a,
            "reviewing",
        )

        question_b = create_review_question(
            session_b,
            "reviewing",
        )

        question_c = create_review_question(
            session_c,
            "reviewing",
        )

        create_source_and_findings(
            session_a,
            question_a,
        )

        create_source_and_findings(
            session_b,
            question_b,
        )

        create_source_and_findings(
            session_c,
            question_c,
        )

        with SessionLocal() as db:

            lease_a = ExecutionLeaseRepository(
                db
            ).acquire(session_a)

            lease_b = ExecutionLeaseRepository(
                db
            ).acquire(session_b)

            lease_c = ExecutionLeaseRepository(
                db
            ).acquire(session_c)

        agent = DeterministicReviewAgent()

        graph = create_graph(
            agent
        )

        # Missing execution lease.

        expect_rejection(
            graph,
            session_a,
            question_a,
            None,
            RuntimeError,
            [question_a],
        )

        assert agent.calls == 0

        print(
            "TEST 1 - Missing lease rejected: PASSED"
        )

        # Mismatched execution lease.

        expect_rejection(
            graph,
            session_a,
            question_a,
            lease_b,
            ValueError,
            [question_a, question_b],
        )

        assert agent.calls == 0

        print(
            "TEST 2 - Mismatched lease rejected: PASSED"
        )

        # Invalid lease owner.

        invalid_lease = replace(
            lease_a,
            owner=str(uuid4()),
        )

        expect_rejection(
            graph,
            session_a,
            question_a,
            invalid_lease,
            ExecutionLeaseFenceRejected,
            [question_a],
        )

        print(
            "TEST 3 - Invalid owner rejected: PASSED"
        )

        # Normal review execution.

        invoke_graph(
            graph,
            session_a,
            question_a,
            lease_a,
        )

        assert agent.calls == 2

        assert get_snapshot(
            question_a
        )[0] == "reviewed"

        assert get_provenance_snapshot(
            question_a
        ) == {
            "reviews": 1,
            "claims": 1,
            "supports": 1,
            "contradicting_references": 0,
            "contradictions": 0,
            "gaps": 0,
        }

        print(
            "TEST 4 - Review persisted through graph: PASSED"
        )

        # A repeated graph invocation must
        # not invoke the Review Agent again.

        calls_before = agent.calls

        invoke_graph(
            graph,
            session_a,
            question_a,
            lease_a,
        )

        assert agent.calls == calls_before

        assert len(
            get_snapshot(question_a)[1]
        ) == 1

        print(
            "TEST 5 - Review retry skips agent: PASSED"
        )

        # Simulate an interrupted lifecycle
        # where the review exists but the
        # question is still reviewing.

        set_question_status(
            question_a,
            "reviewing",
        )

        invoke_graph(
            graph,
            session_a,
            question_a,
            lease_a,
        )

        assert agent.calls == calls_before

        assert get_snapshot(
            question_a
        )[0] == "reviewed"

        print(
            "TEST 6 - Existing review recovery: PASSED"
        )

        # Expired execution lease.

        expire_lease(
            session_b
        )

        calls_before = agent.calls

        expect_rejection(
            graph,
            session_b,
            question_b,
            lease_b,
            ExecutionLeaseFenceRejected,
            [question_b],
        )

        assert agent.calls == calls_before + 1

        print(
            "TEST 7 - Expired lease blocks persistence: PASSED"
        )

        # Superseded execution lease.

        with SessionLocal() as db:

            replacement_lease_b = (
                ExecutionLeaseRepository(db)
                .acquire(session_b)
            )

        calls_before = agent.calls

        expect_rejection(
            graph,
            session_b,
            question_b,
            lease_b,
            ExecutionLeaseFenceRejected,
            [question_b],
        )

        assert agent.calls == calls_before + 1

        print(
            "TEST 8 - Superseded lease blocks persistence: PASSED"
        )

        # A replacement worker may persist
        # the review successfully.

        invoke_graph(
            graph,
            session_b,
            question_b,
            replacement_lease_b,
        )

        assert get_snapshot(
            question_b
        )[0] == "reviewed"

        assert get_provenance_snapshot(
            question_b
        )["reviews"] == 1

        print(
            "TEST 9 - Replacement lease succeeds: PASSED"
        )

        # Cross-session question must not
        # be persisted using another session.

        expect_rejection(
            graph,
            session_c,
            question_a,
            lease_c,
            ValueError,
            [question_a, question_c],
        )

        print(
            "TEST 10 - Cross-session question rejected: PASSED"
        )

        # The untouched session must remain
        # unchanged by other executions.

        assert get_snapshot(
            question_c
        )[0] == "reviewing"

        assert get_provenance_snapshot(
            question_c
        )["reviews"] == 0

        print(
            "TEST 11 - Session isolation preserved: PASSED"
        )

        print()
        print("PASS")

    finally:

        for session_id in reversed(
            sessions
        ):

            delete_provenance(
                session_id
            )

            delete_session(
                session_id
            )


if __name__ == "__main__":

    main()
