
from domain.report import (
    ResearchReport,
    ReportSection,
)

from langgraph.graph import (
    StateGraph,
    START,
    END,
)

from graph.state import (
    ResearchState,
)

from nodes.generate_report import (
    GenerateReportNode,
)

from persistence.database import (
    SessionLocal,
)

from persistence.execution_lease_repository import (
    ExecutionLeaseFenceRejected,
)

from persistence.report_repository import (
    ReportRepository,
)

from processing.report_context_builder import (
    ReportContextBuilder,
)

from processing.report_validator import (
    ReportValidator,
)

from test_search_result_fencing import (
    create_session,
    delete_session,
    expire_lease,
)

from test_review_completion_fencing import (
    acquire_lease,
)

from test_review_selection_fencing import (
    set_session_status,
)

from test_report_persistence_fencing import (
    delete_report,
)

from test_report_provenance_rollback import (
    create_reviewed_claims,
    delete_review_fixture,
)


class DeterministicReportAgent:

    def __init__(
        self,
        claim_ids,
        on_generate=None,
    ):

        self.claim_ids = list(
            claim_ids
        )

        self.on_generate = (
            on_generate
        )

        self.calls = 0

        self.last_topic = None
        self.last_evidence = None

    def generate(
        self,
        topic,
        reviewed_evidence,
    ):

        self.calls += 1

        self.last_topic = topic

        self.last_evidence = (
            reviewed_evidence
        )

        if self.on_generate is not None:

            self.on_generate()

        return ResearchReport(
            title="Deterministic Graph Report",
            executive_summary=(
                "A reproducible integration test."
            ),
            sections=[
                ReportSection(
                    heading="Reviewed Evidence",
                    content=(
                        "The report uses persisted "
                        "reviewed claims."
                    ),
                    reviewed_claim_ids=(
                        self.claim_ids
                    ),
                ),
            ],
            conclusions=(
                "Conclusions based on reviewed "
                "research evidence."
            ),
            limitations=[
                "Limited test evidence.",
            ],
        )


def create_graph(
    report_agent,
):

    builder = StateGraph(
        ResearchState
    )

    builder.add_node(
        "generate_report",
        GenerateReportNode(
            session_factory=SessionLocal,
            report_agent=report_agent,
            context_builder=(
                ReportContextBuilder()
            ),
            validator=(
                ReportValidator()
            ),
        ),
    )

    builder.add_edge(
        START,
        "generate_report",
    )

    builder.add_edge(
        "generate_report",
        END,
    )

    return builder.compile()


def invoke_graph(
    graph,
    session_id,
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
            "topic": "Deterministic report research",
        },
        config={
            "configurable": configurable,
        },
    )


def load_report(
    session_id,
):

    with SessionLocal() as db:

        return ReportRepository(
            db
        ).get_for_session(
            session_id
        )


def expect_rejection(
    graph,
    session_id,
    lease,
    expected_exception,
):

    before = load_report(
        session_id
    )

    try:

        invoke_graph(
            graph,
            session_id,
            lease,
        )

    except expected_exception:

        pass

    else:

        raise AssertionError(
            "Graph execution was "
            "unexpectedly accepted."
        )

    after = load_report(
        session_id
    )

    assert after == before, (
        "Rejected graph execution "
        "modified persisted report state."
    )


def main():

    print()
    print("GRAPH REPORT GENERATION")
    print("=======================")

    sessions = []
    review_questions = {}

    try:

        session_a = create_session()
        sessions.append(session_a)

        session_b = create_session()
        sessions.append(session_b)

        session_c = create_session()
        sessions.append(session_c)

        session_d = create_session()
        sessions.append(session_d)

        for session_id in sessions:

            set_session_status(
                session_id,
                "reviewed",
            )

            question_id, claim_ids = (
                create_reviewed_claims(
                    session_id
                )
            )

            review_questions[
                session_id
            ] = question_id

            if session_id == session_a:

                claims_a = claim_ids

            elif session_id == session_b:

                claims_b = claim_ids

            elif session_id == session_c:

                claims_c = claim_ids

            else:

                claims_d = claim_ids

        lease_a = acquire_lease(
            session_a
        )

        lease_b = acquire_lease(
            session_b
        )

        lease_c = acquire_lease(
            session_c
        )

        lease_d = acquire_lease(
            session_d
        )

        #
        # Successful graph execution.
        #

        agent_a = DeterministicReportAgent(
            claims_a
        )

        graph_a = create_graph(
            agent_a
        )

        invoke_graph(
            graph_a,
            session_a,
            lease_a,
        )

        persisted_a = load_report(
            session_a
        )

        assert persisted_a is not None

        assert agent_a.calls == 1

        assert (
            persisted_a.sections[0]
            .reviewed_claim_ids
            == sorted(claims_a)
        )

        print(
            "TEST 1 - Graph report persisted: PASSED"
        )

        #
        # Verify reviewed evidence reached
        # the Report Agent.
        #

        assert agent_a.last_topic == (
            "Deterministic report research"
        )

        for claim_id in claims_a:

            assert (
                f"REVIEWED CLAIM ID: {claim_id}"
                in agent_a.last_evidence
            )

        print(
            "TEST 2 - Reviewed evidence supplied: PASSED"
        )

        #
        # Idempotent graph retry.
        #

        invoke_graph(
            graph_a,
            session_a,
            lease_a,
        )

        assert agent_a.calls == 1

        assert load_report(
            session_a
        ) == persisted_a

        print(
            "TEST 3 - Existing report recovery: PASSED"
        )

        #
        # Missing execution lease.
        #

        agent_missing = (
            DeterministicReportAgent(
                claims_b
            )
        )

        graph_missing = create_graph(
            agent_missing
        )

        expect_rejection(
            graph_missing,
            session_b,
            None,
            RuntimeError,
        )

        assert agent_missing.calls == 0

        print(
            "TEST 4 - Missing lease rejected: PASSED"
        )

        #
        # Invalid lifecycle state.
        #

        set_session_status(
            session_b,
            "researched",
        )

        expect_rejection(
            graph_missing,
            session_b,
            lease_b,
            ValueError,
        )

        assert agent_missing.calls == 0

        set_session_status(
            session_b,
            "reviewed",
        )

        print(
            "TEST 5 - Invalid lifecycle rejected: PASSED"
        )

        #
        # Lease replacement during generation.
        #

        replacement = {
            "lease": None,
        }

        def replace_lease():

            expire_lease(
                session_b
            )

            replacement["lease"] = (
                acquire_lease(
                    session_b
                )
            )

        stale_agent = (
            DeterministicReportAgent(
                claims_b,
                on_generate=replace_lease,
            )
        )

        stale_graph = create_graph(
            stale_agent
        )

        expect_rejection(
            stale_graph,
            session_b,
            lease_b,
            ExecutionLeaseFenceRejected,
        )

        assert stale_agent.calls == 1

        assert replacement["lease"] is not None

        assert load_report(
            session_b
        ) is None

        print(
            "TEST 6 - Superseded worker rejected: PASSED"
        )

        #
        # Replacement worker completes
        # report generation.
        #

        replacement_agent = (
            DeterministicReportAgent(
                claims_b
            )
        )

        replacement_graph = create_graph(
            replacement_agent
        )

        invoke_graph(
            replacement_graph,
            session_b,
            replacement["lease"],
        )

        assert replacement_agent.calls == 1

        assert load_report(
            session_b
        ) is not None

        print(
            "TEST 7 - Replacement worker succeeds: PASSED"
        )

        #
        # Invalid model provenance.
        #

        invalid_agent = (
            DeterministicReportAgent(
                [2147483647]
            )
        )

        invalid_graph = create_graph(
            invalid_agent
        )

        expect_rejection(
            invalid_graph,
            session_c,
            lease_c,
            ValueError,
        )

        assert invalid_agent.calls == 1

        assert load_report(
            session_c
        ) is None

        print(
            "TEST 8 - Invalid model provenance rejected: PASSED"
        )

        #
        # A valid worker can retry after
        # model-output validation failure.
        #

        valid_agent = (
            DeterministicReportAgent(
                claims_c
            )
        )

        valid_graph = create_graph(
            valid_agent
        )

        invoke_graph(
            valid_graph,
            session_c,
            lease_c,
        )

        assert load_report(
            session_c
        ) is not None

        print(
            "TEST 9 - Retry after validation failure: PASSED"
        )

        #
        # Cross-session lease.
        #

        agent_d = DeterministicReportAgent(
            claims_d
        )

        graph_d = create_graph(
            agent_d
        )

        expect_rejection(
            graph_d,
            session_d,
            lease_a,
            ValueError,
        )

        assert agent_d.calls == 0

        print(
            "TEST 10 - Cross-session lease rejected: PASSED"
        )

        #
        # Session isolation.
        #

        assert load_report(
            session_a
        ) is not None

        assert load_report(
            session_b
        ) is not None

        assert load_report(
            session_c
        ) is not None

        assert load_report(
            session_d
        ) is None

        print(
            "TEST 11 - Session isolation preserved: PASSED"
        )

        print()
        print("PASS")

    finally:

        for session_id in reversed(
            sessions
        ):

            delete_report(
                session_id
            )

            if session_id in review_questions:

                delete_review_fixture(
                    review_questions[
                        session_id
                    ]
                )

            delete_session(
                session_id
            )


if __name__ == "__main__":

    main()
