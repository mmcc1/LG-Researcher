from unittest.mock import Mock

import pytest

from agents.source_summariser import (
    SourceSummariser,
)

from processing.source_context_builder import (
    SourceContextBuilder,
)


TEST_QUESTION = "What does the source establish?"


@pytest.mark.parametrize(
    "source_text",
    [
        "",
        " ",
        "\t\r\n ",
    ],
)
@pytest.mark.parametrize(
    "chunking_enabled",
    [
        True,
        False,
    ],
)
def test_empty_source_returns_empty_context(
    source_text,
    chunking_enabled,
):

    chunker = Mock()

    ranker = Mock()

    builder = SourceContextBuilder(
        chunker=chunker,
        ranker=ranker,
        chunking_enabled=chunking_enabled,
    )

    result = builder.build(
        question=TEST_QUESTION,
        source_text=source_text,
    )

    assert result == (
        "",
        0,
        0,
    )

    assert not chunker.mock_calls

    assert not ranker.mock_calls


def test_valid_unchunked_context():

    chunker = Mock()

    ranker = Mock()

    builder = SourceContextBuilder(
        chunker=chunker,
        ranker=ranker,
        chunking_enabled=False,
    )

    result = builder.build(
        question=TEST_QUESTION,
        source_text="  Valid research evidence.  ",
    )

    assert result == (
        "Valid research evidence.",
        1,
        1,
    )

    assert not chunker.mock_calls

    assert not ranker.mock_calls


def test_unchunked_context_respects_character_limit():

    builder = SourceContextBuilder(
        chunker=Mock(),
        ranker=Mock(),
        max_characters=8,
        chunking_enabled=False,
    )

    result = builder.build(
        question=TEST_QUESTION,
        source_text="Research evidence.",
    )

    assert result == (
        "Research",
        1,
        1,
    )


@pytest.mark.parametrize(
    "source_text",
    [
        "",
        " ",
        "\t\r\n ",
    ],
)
def test_summariser_rejects_empty_context(
    source_text,
):

    model = Mock()

    structured_model = (
        model.with_structured_output.return_value
    )

    summariser = SourceSummariser(
        model=model,
    )

    with pytest.raises(
        ValueError,
        match="no usable research context",
    ):

        summariser.analyse(
            research_question=TEST_QUESTION,
            source_title="Test source",
            source_url="https://example.com/test",
            source_text=source_text,
        )

    structured_model.invoke.assert_not_called()


def test_summariser_accepts_valid_context():

    model = Mock()

    structured_model = (
        model.with_structured_output.return_value
    )

    expected_analysis = Mock()

    structured_model.invoke.return_value = (
        expected_analysis
    )

    summariser = SourceSummariser(
        model=model,
    )

    result = summariser.analyse(
        research_question=TEST_QUESTION,
        source_title="Test source",
        source_url="https://example.com/test",
        source_text="Valid research evidence.",
    )

    assert result is expected_analysis

    structured_model.invoke.assert_called_once()