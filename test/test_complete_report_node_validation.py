from datetime import (
    datetime,
    timedelta,
    timezone,
)

from types import SimpleNamespace

from unittest.mock import (
    MagicMock,
    Mock,
    patch,
)

from uuid import uuid4

import pytest

from application.report_file_writer import (
    ReportFileWriter,
)

from domain.report import (
    PersistedResearchReport,
    PersistedReportSection,
)

from nodes.complete_report import (
    CompleteReportNode,
)

from persistence.execution_lease_repository import (
    ExecutionLease,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)

from persistence.models import (
    ReviewedClaimEntity,
    ReviewedClaimSupport,
    ReviewedClaimContradiction,
)


SESSION_ID = str(uuid4())

QUESTION_ID = 101

CLAIM_ID = 201

SUPPORTING_FINDING_ID = 301

CONTRADICTING_FINDING_ID = 302

SUPPORTING_SOURCE_ID = 401

CONTRADICTING_SOURCE_ID = 402

SECTION_ID = 501


def make_lease(
    session_id=SESSION_ID,
):

    return ExecutionLease(
        session_id=session_id,
        owner="isolated-test-owner",
        version=1,
        expires_at=(
            datetime.now(timezone.utc)
            + timedelta(minutes=5)
        ),
    )


def make_report():

    return PersistedResearchReport(
        id=1,
        research_session_id=SESSION_ID,
        title="Research report — Étude scientifique",
        executive_summary="Test executive summary.",
        sections=[
            PersistedReportSection(
                id=SECTION_ID,
                ordinal=1,
                heading="Research findings",
                content="Research content — 科学研究",
                reviewed_claim_ids=[
                    CLAIM_ID
                ],
            ),
        ],
        conclusions="Test conclusions.",
        limitations=[
            "Limited evidence."
        ],
    )


def make_source(
    source_id,
    title,
):

    url = (
        f"https://example.com/source/{source_id}"
    )

    return SimpleNamespace(
        id=source_id,
        research_session_id=SESSION_ID,
        research_question_id=QUESTION_ID,
        title=title,
        requested_url=url,
        final_url=url,
        extracted_text="Valid research evidence.",
        content_hash="0" * 64,
    )


def make_finding(
    finding_id,
    source_id,
):

    return SimpleNamespace(
        id=finding_id,
        source_id=source_id,
        research_question_id=QUESTION_ID,
    )


def make_claim_query():

    query = MagicMock()

    query.join.return_value = query

    query.filter.return_value = query

    query.all.return_value = [
        (
            CLAIM_ID,
        )
    ]

    return query


def make_evidence_query(
    finding,
    source,
):

    query = MagicMock()

    query.select_from.return_value = query

    query.join.return_value = query

    query.outerjoin.return_value = query

    query.filter.return_value = query

    query.order_by.return_value = query

    query.all.return_value = [
        (
            CLAIM_ID,
            finding.id,
            QUESTION_ID,
            finding,
            source,
        )
    ]

    return query


@pytest.fixture
def environment(
    tmp_path,
):

    report = make_report()

    supporting_source = make_source(
        source_id=SUPPORTING_SOURCE_ID,
        title="Supporting publication",
    )

    contradicting_source = make_source(
        source_id=CONTRADICTING_SOURCE_ID,
        title="Contradicting publication",
    )

    supporting_finding = make_finding(
        finding_id=SUPPORTING_FINDING_ID,
        source_id=SUPPORTING_SOURCE_ID,
    )

    contradicting_finding = make_finding(
        finding_id=CONTRADICTING_FINDING_ID,
        source_id=CONTRADICTING_SOURCE_ID,
    )

    claim_query = make_claim_query()

    supporting_query = make_evidence_query(
        finding=supporting_finding,
        source=supporting_source,
    )

    contradicting_query = make_evidence_query(
        finding=contradicting_finding,
        source=contradicting_source,
    )

    db = MagicMock()

    def next_query(
        *args,
        **kwargs,
    ):

        if args:

            first_column = args[0]

            if first_column is ReviewedClaimEntity.id:

                return claim_query

            if first_column is ReviewedClaimSupport.reviewed_claim_id:

                return supporting_query

            if first_column is ReviewedClaimContradiction.reviewed_claim_id:

                return contradicting_query

        raise AssertionError(
            f"Unexpected database query: {args}"
        )

    db.query.side_effect = (
        next_query
    )

    session_context = MagicMock()

    session_context.__enter__.return_value = db

    session_context.__exit__.return_value = False

    session_factory = Mock(
        return_value=session_context,
    )

    lease = make_lease()

    node = CompleteReportNode(
        session_factory=session_factory,
    )

    node.report_file_writer = (
        ReportFileWriter(
            output_directory=tmp_path,
        )
    )

    output_path = (
        tmp_path
        / f"{SESSION_ID}.txt"
    )

    execution_guard = Mock()

    with patch(
        "nodes.complete_report.ReportRepository",
    ) as repository_class:

        repository = (
            repository_class.return_value
        )

        repository.get_for_session.return_value = (
            report
        )

        with patch.object(
            ResearchSessionRepository,
            "complete_report_fenced",
            autospec=True,
        ) as complete_report:

            with patch.object(
                node.report_file_writer,
                "write",
                wraps=node.report_file_writer.write,
            ) as write_report:

                yield SimpleNamespace(
                    node=node,
                    report=report,
                    lease=lease,
                    execution_guard=execution_guard,
                    session_factory=session_factory,
                    repository=repository,
                    complete_report=complete_report,
                    write_report=write_report,
                    output_directory=tmp_path,
                    output_path=output_path,
                    supporting_source=supporting_source,
                    contradicting_source=contradicting_source,
                    supporting_finding=supporting_finding,
                    contradicting_finding=contradicting_finding,
                    claim_query=claim_query,
                    supporting_query=supporting_query,
                    contradicting_query=contradicting_query,
                )


def execute_node(
    environment,
):

    result = environment.node(
        state={
            "session_id": SESSION_ID,
        },
        config={
            "configurable": {
                "execution_lease": environment.lease,
                "execution_guard": (
                    environment.execution_guard
                ),
            },
        },
    )

    return result


def assert_no_publication(
    environment,
):

    environment.write_report.assert_not_called()

    environment.complete_report.assert_not_called()

    assert not (
        environment.output_path.exists()
    )

    assert not list(
        environment.output_directory.iterdir()
    )


def assert_successful_completion(
    environment,
):

    assert environment.output_path.is_file()

    environment.complete_report.assert_called_once()

    arguments = (
        environment.complete_report.call_args.kwargs
    )

    assert (
        arguments["session_id"]
        == SESSION_ID
    )

    assert (
        arguments["lease"]
        == environment.lease
    )

    assert list(
        environment.output_directory.iterdir()
    ) == [
        environment.output_path
    ]

    report_text = (
        environment.output_path.read_text(
            encoding="utf-8"
        )
    )

    assert "BIBLIOGRAPHY" in report_text

    assert "Sources cited: [1]" in report_text

    assert (
        "Contradicting evidence: [2]"
        in report_text
    )

    return report_text


def test_successful_report_completion(
    environment,
):

    events = []

    def execution_guard():

        events.append(
            "guard"
        )

    environment.execution_guard.side_effect = (
        execution_guard
    )

    writer = environment.node.report_file_writer

    original_write = ReportFileWriter.write

    def tracked_write(
        session_id,
        report_text,
    ):

        events.append(
            "write"
        )

        return original_write(
            writer,
            session_id=session_id,
            report_text=report_text,
        )

    environment.write_report.side_effect = (
        tracked_write
    )

    def complete_report(
        repository,
        session_id,
        lease,
    ):

        assert environment.output_path.is_file()

        events.append(
            "complete"
        )

    environment.complete_report.side_effect = (
        complete_report
    )

    result = execute_node(
        environment
    )

    assert result == {}

    assert events == [
        "guard",
        "guard",
        "write",
        "guard",
        "complete",
    ]

    assert_successful_completion(
        environment
    )


@pytest.mark.parametrize(
    "configuration",
    [
        {},
        {
            "configurable": {}
        },
        {
            "configurable": {
                "execution_lease": None,
            },
        },
        {
            "configurable": {
                "execution_lease": "invalid-lease",
            },
        },
    ],
)
def test_missing_or_invalid_lease_rejected(
    environment,
    configuration,
):

    with pytest.raises(
        RuntimeError,
        match=(
            "Execution lease is missing "
            "from graph configuration."
        ),
    ):

        environment.node(
            state={
                "session_id": SESSION_ID,
            },
            config=configuration,
        )

    environment.session_factory.assert_not_called()

    assert_no_publication(
        environment
    )


def test_mismatched_lease_rejected(
    environment,
):

    environment.lease = make_lease(
        session_id=str(uuid4()),
    )

    with pytest.raises(
        ValueError,
        match=(
            "Execution lease does not match "
            "the research session."
        ),
    ):

        execute_node(
            environment
        )

    environment.session_factory.assert_not_called()

    assert_no_publication(
        environment
    )


def test_non_callable_guard_rejected(
    environment,
):

    environment.execution_guard = (
        "invalid-guard"
    )

    with pytest.raises(
        TypeError,
        match=(
            "Execution guard must be callable."
        ),
    ):

        execute_node(
            environment
        )

    environment.session_factory.assert_not_called()

    assert_no_publication(
        environment
    )


def test_missing_persisted_report_rejected(
    environment,
):

    environment.repository.get_for_session.return_value = (
        None
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "Cannot complete research session "
            "because no persisted report exists."
        ),
    ):

        execute_node(
            environment
        )

    assert_no_publication(
        environment
    )


@pytest.mark.parametrize(
    "relationship",
    [
        "supporting",
        "contradicting",
    ],
)
@pytest.mark.parametrize(
    "extracted_text",
    [
        "",
        " ",
        "\t\r\n ",
    ],
)
def test_unusable_evidence_prevents_completion(
    environment,
    relationship,
    extracted_text,
):

    if relationship == "supporting":

        source = (
            environment.supporting_source
        )

    else:

        source = (
            environment.contradicting_source
        )

    source.extracted_text = (
        extracted_text
    )

    expected_message = (
        "a source containing no usable "
        f"research text: {source.id}"
    )

    with pytest.raises(
        ValueError,
        match=expected_message,
    ):

        execute_node(
            environment
        )

    assert_no_publication(
        environment
    )

    assert (
        environment.execution_guard.call_count
        == 1
    )


@pytest.mark.parametrize(
    "relationship",
    [
        "supporting",
        "contradicting",
    ],
)
def test_foreign_finding_prevents_completion(
    environment,
    relationship,
):

    if relationship == "supporting":

        finding = (
            environment.supporting_finding
        )

    else:

        finding = (
            environment.contradicting_finding
        )

    finding.research_question_id = (
        QUESTION_ID + 1
    )

    with pytest.raises(
        ValueError,
        match=(
            f"finding {finding.id} "
            "belonging to another research question."
        ),
    ):

        execute_node(
            environment
        )

    assert_no_publication(
        environment
    )


@pytest.mark.parametrize(
    "relationship",
    [
        "supporting",
        "contradicting",
    ],
)
def test_foreign_source_prevents_completion(
    environment,
    relationship,
):

    if relationship == "supporting":

        source = (
            environment.supporting_source
        )

    else:

        source = (
            environment.contradicting_source
        )

    source.research_question_id = (
        QUESTION_ID + 1
    )

    with pytest.raises(
        ValueError,
        match=(
            f"source {source.id} "
            "outside the current research question."
        ),
    ):

        execute_node(
            environment
        )

    assert_no_publication(
        environment
    )


def test_foreign_reviewed_claim_rejected(
    environment,
):

    environment.claim_query.all.return_value = []

    with pytest.raises(
        ValueError,
        match=(
            "Reviewed claims do not belong "
            "to the requested research session"
        ),
    ):

        execute_node(
            environment
        )

    assert_no_publication(
        environment
    )


def test_missing_supporting_evidence_rejected(
    environment,
):

    environment.supporting_query.all.return_value = []

    with pytest.raises(
        ValueError,
        match=(
            "Reviewed claim has no resolvable "
            "supporting source"
        ),
    ):

        execute_node(
            environment
        )

    assert_no_publication(
        environment
    )


def test_registry_failure_prevents_publication(
    environment,
):

    environment.supporting_source.final_url = (
        "ftp://example.com/unsupported"
    )

    with pytest.raises(
        ValueError,
        match=(
            "Citation source has an "
            "unsupported URL scheme"
        ),
    ):

        execute_node(
            environment
        )

    assert_no_publication(
        environment
    )


def test_formatter_failure_prevents_publication(
    environment,
):

    with patch.object(
        environment.node.report_formatter,
        "format",
        side_effect=ValueError(
            "Simulated formatter failure."
        ),
    ):

        with pytest.raises(
            ValueError,
            match="Simulated formatter failure.",
        ):

            execute_node(
                environment
            )

    assert_no_publication(
        environment
    )


@pytest.mark.parametrize(
    "relationship",
    [
        "supporting",
        "contradicting",
    ],
)
def test_valid_untitled_source_completes(
    environment,
    relationship,
):

    if relationship == "supporting":

        source = (
            environment.supporting_source
        )

        expected_number = 1

    else:

        source = (
            environment.contradicting_source
        )

        expected_number = 2

    source.title = ""

    result = execute_node(
        environment
    )

    assert result == {}

    report_text = assert_successful_completion(
        environment
    )

    expected_text = (
        f"[{expected_number}] {source.final_url}\n"
        f"{source.final_url}"
    )

    assert expected_text in report_text


def test_unicode_report_publication(
    environment,
):

    result = execute_node(
        environment
    )

    assert result == {}

    report_text = assert_successful_completion(
        environment
    )

    assert environment.report.title in report_text

    assert (
        environment.report.sections[0].content
        in report_text
    )

    assert (
        environment.output_path.read_bytes()
        == report_text.encode("utf-8")
    )


@pytest.mark.parametrize(
    "failed_guard_call",
    [
        1,
        2,
    ],
)
def test_guard_failure_before_publication(
    environment,
    failed_guard_call,
):

    guard_results = (
        [None] * (failed_guard_call - 1)
    )

    guard_results.append(
        RuntimeError(
            "Simulated execution guard rejection."
        )
    )

    environment.execution_guard.side_effect = (
        guard_results
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "Simulated execution guard rejection."
        ),
    ):

        execute_node(
            environment
        )

    assert (
        environment.execution_guard.call_count
        == failed_guard_call
    )

    if failed_guard_call == 1:

        environment.session_factory.assert_not_called()

    assert_no_publication(
        environment
    )


def test_guard_failure_after_publication(
    environment,
):

    environment.execution_guard.side_effect = [
        None,
        None,
        RuntimeError(
            "Execution lease lost after publication."
        ),
    ]

    with pytest.raises(
        RuntimeError,
        match=(
            "Execution lease lost after publication."
        ),
    ):

        execute_node(
            environment
        )

    environment.write_report.assert_called_once()

    environment.complete_report.assert_not_called()

    assert environment.output_path.is_file()

    report_text = (
        environment.output_path.read_text(
            encoding="utf-8"
        )
    )

    assert "BIBLIOGRAPHY" in report_text


def test_file_writer_failure_prevents_completion(
    environment,
):

    with patch(
        "application.report_file_writer.os.replace",
        side_effect=OSError(
            "Simulated file replacement failure."
        ),
    ):

        with pytest.raises(
            OSError,
            match=(
                "Simulated file replacement failure."
            ),
        ):

            execute_node(
                environment
            )

    environment.write_report.assert_called_once()

    environment.complete_report.assert_not_called()

    assert not environment.output_path.exists()

    assert not list(
        environment.output_directory.iterdir()
    )


def test_database_completion_failure_preserves_report(
    environment,
):

    environment.complete_report.side_effect = (
        RuntimeError(
            "Simulated database completion failure."
        )
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "Simulated database completion failure."
        ),
    ):

        execute_node(
            environment
        )

    environment.write_report.assert_called_once()

    environment.complete_report.assert_called_once()

    assert environment.output_path.is_file()

    report_text = (
        environment.output_path.read_text(
            encoding="utf-8"
        )
    )

    assert "BIBLIOGRAPHY" in report_text

    assert "Sources cited: [1]" in report_text


def test_retry_after_database_completion_failure(
    environment,
):

    environment.complete_report.side_effect = (
        RuntimeError(
            "Simulated database completion failure."
        )
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "Simulated database completion failure."
        ),
    ):

        execute_node(
            environment
        )

    assert environment.output_path.is_file()

    original_content = (
        environment.output_path.read_bytes()
    )

    environment.complete_report.reset_mock()

    environment.complete_report.side_effect = None

    environment.write_report.reset_mock()

    environment.execution_guard.reset_mock()

    result = execute_node(
        environment
    )

    assert result == {}

    environment.write_report.assert_called_once()

    assert_successful_completion(
        environment
    )

    assert (
        environment.output_path.read_bytes()
        == original_content
    )

    assert (
        environment.repository.get_for_session.call_count
        == 2
    )


def test_retry_after_guard_failure(
    environment,
):

    environment.execution_guard.side_effect = [
        None,
        None,
        RuntimeError(
            "Execution lease lost after publication."
        ),
    ]

    with pytest.raises(
        RuntimeError,
        match=(
            "Execution lease lost after publication."
        ),
    ):

        execute_node(
            environment
        )

    environment.complete_report.assert_not_called()

    original_content = (
        environment.output_path.read_bytes()
    )

    environment.execution_guard.reset_mock()

    environment.execution_guard.side_effect = None

    environment.write_report.reset_mock()

    environment.lease = ExecutionLease(
        session_id=SESSION_ID,
        owner="recovery-test-owner",
        version=2,
        expires_at=(
            datetime.now(timezone.utc)
            + timedelta(minutes=5)
        ),
    )

    result = execute_node(
        environment
    )

    assert result == {}

    assert_successful_completion(
        environment
    )

    assert (
        environment.output_path.read_bytes()
        == original_content
    )


@pytest.mark.parametrize(
    "relationship",
    [
        "supporting",
        "contradicting",
    ],
)
def test_retry_after_evidence_restoration(
    environment,
    relationship,
):

    if relationship == "supporting":

        source = (
            environment.supporting_source
        )

    else:

        source = (
            environment.contradicting_source
        )

    original_text = (
        source.extracted_text
    )

    source.extracted_text = ""

    with pytest.raises(
        ValueError,
        match=(
            "a source containing no usable research text"
        ),
    ):

        execute_node(
            environment
        )

    assert_no_publication(
        environment
    )

    source.extracted_text = (
        original_text
    )

    environment.execution_guard.reset_mock()

    result = execute_node(
        environment
    )

    assert result == {}

    assert_successful_completion(
        environment
    )


def test_completion_without_optional_guard(
    environment,
):

    environment.execution_guard = None

    result = execute_node(
        environment
    )

    assert result == {}

    assert_successful_completion(
        environment
    )


def test_invalid_evidence_preserves_existing_file(
    environment,
):

    original_text = (
        "Previously published research report."
    )

    environment.output_path.write_text(
        original_text,
        encoding="utf-8",
    )

    environment.supporting_source.extracted_text = ""

    with pytest.raises(
        ValueError,
        match=(
            "a source containing no usable research text"
        ),
    ):

        execute_node(
            environment
        )

    environment.write_report.assert_not_called()

    environment.complete_report.assert_not_called()

    assert (
        environment.output_path.read_text(
            encoding="utf-8"
        )
        == original_text
    )

    assert list(
        environment.output_directory.iterdir()
    ) == [
        environment.output_path
    ]


def test_persisted_report_data_not_mutated(
    environment,
):

    original_report = (
        environment.report.model_dump()
    )

    result = execute_node(
        environment
    )

    assert result == {}

    assert_successful_completion(
        environment
    )

    assert (
        environment.report.model_dump()
        == original_report
    )