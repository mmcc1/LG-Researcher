import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class ModelSettings:
    provider: str
    model_name: str
    base_url: str | None
    temperature: float | None
    timeout_seconds: float = 900.0
    api_key: str | None = None


@dataclass(frozen=True)
class DatabaseSettings:
    server: str
    port: int
    database: str
    username: str
    password: str
    driver: str
    trust_server_certificate: str


@dataclass(frozen=True)
class ResearchSettings:
    question_count: int
    search_max_queries: int
    search_results_per_query: int
    retrieval_max_sources: int
    text_chunking_enabled: bool
    text_chunk_size: int
    text_chunk_overlap: int
    source_context_max_chunks: int
    source_context_max_characters: int
    report_target_word_count: int
    report_min_word_count: int
    report_max_word_count: int

    def __post_init__(self):

        positive_values = {
            "question_count": self.question_count,
            "search_max_queries": self.search_max_queries,
            "search_results_per_query": self.search_results_per_query,
            "retrieval_max_sources": self.retrieval_max_sources,
            "text_chunk_size": self.text_chunk_size,
            "source_context_max_chunks": self.source_context_max_chunks,
            "source_context_max_characters": self.source_context_max_characters,
            "report_target_word_count": self.report_target_word_count,
            "report_min_word_count": self.report_min_word_count,
            "report_max_word_count": self.report_max_word_count,
        }

        for name, value in positive_values.items():

            if value <= 0:
                raise ValueError(
                    f"{name} must be greater than zero."
                )

        if not (
            0 <= self.text_chunk_overlap
            < self.text_chunk_size
        ):
            raise ValueError(
                "text_chunk_overlap must be non-negative "
                "and smaller than text_chunk_size."
            )

        if not (
            self.report_min_word_count
            <= self.report_target_word_count
            <= self.report_max_word_count
        ):
            raise ValueError(
                "Report word counts must satisfy "
                "minimum <= target <= maximum."
            )


@dataclass(frozen=True)
class Settings:
    planner_model: ModelSettings
    researcher_model: ModelSettings
    summariser_model: ModelSettings
    reviewer_model: ModelSettings
    reporter_model: ModelSettings
    controller_model: ModelSettings

    database: DatabaseSettings
    report_output_directory: str
    research: ResearchSettings


def create_model_settings(
    prefix: str,
) -> ModelSettings:

    provider = os.getenv(
        f"{prefix}_PROVIDER",
        os.getenv(
            "LLM_PROVIDER",
            "ollama",
        ),
    ).strip().lower()

    if provider not in {
        "ollama",
        "openai",
    }:

        raise ValueError(
            f"Unsupported model provider for "
            f"{prefix}: {provider}"
        )

    if provider == "ollama":

        default_model = "qwen3:8b"

        default_base_url = (
            "http://localhost:11434"
        )

        default_temperature = "0.2"

    else:

        default_model = "gpt-4.1-mini"

        default_base_url = None

        default_temperature = None

    model_name = os.getenv(
        f"{prefix}_MODEL",
        default_model,
    )

    base_url = os.getenv(
        f"{prefix}_BASE_URL",
        default_base_url,
    )

    temperature_text = os.getenv(
        f"{prefix}_TEMPERATURE",
        default_temperature,
    )

    if (
        temperature_text is None
        or not temperature_text.strip()
    ):

        temperature = None

    else:

        temperature = float(
            temperature_text
        )

    api_key = None

    if provider == "openai":

        api_key = os.getenv(
            "OPENAI_API_KEY",
        )

    return ModelSettings(
        provider=provider,
        model_name=model_name,
        base_url=base_url,
        temperature=temperature,
        timeout_seconds=float(
            os.getenv(
                f"{prefix}_TIMEOUT_SECONDS",
                "900",
            )
        ),
        api_key=api_key,
    )


def get_boolean_setting(
    name: str,
    default: bool,
) -> bool:

    default_text = (
        "true" if default else "false"
    )

    value = os.getenv(
        name,
        default_text,
    ).strip().lower()

    if value in {
        "true",
        "1",
        "yes",
        "on",
    }:
        return True

    if value in {
        "false",
        "0",
        "no",
        "off",
    }:
        return False

    raise ValueError(
        f"Invalid boolean value for {name}: {value}"
    )


settings = Settings(

    planner_model=create_model_settings("PLANNER"),
    researcher_model=create_model_settings("RESEARCHER"),
    summariser_model=create_model_settings("SUMMARISER"),
    reviewer_model=create_model_settings("REVIEWER"),
    reporter_model=create_model_settings("REPORTER"),
    controller_model=create_model_settings("CONTROLLER"),

    database=DatabaseSettings(
        server=os.getenv("DB_SERVER", "localhost"),
        port=int(os.getenv("DB_PORT", "1433")),
        database=os.getenv("DB_NAME", "Researcher"),
        username=os.getenv("DB_USERNAME", ""),
        password=os.getenv("DB_PASSWORD", ""),
        driver=os.getenv(
            "DB_DRIVER",
            "ODBC Driver 18 for SQL Server",
        ),
        trust_server_certificate=os.getenv(
            "DB_TRUST_SERVER_CERTIFICATE",
            "yes",
        ),
    ),
    research=ResearchSettings(
        question_count=int(
            os.getenv("RESEARCH_QUESTION_COUNT", "8")
        ),
        search_max_queries=int(
            os.getenv("SEARCH_MAX_QUERIES", "3")
        ),
        search_results_per_query=int(
            os.getenv("SEARCH_RESULTS_PER_QUERY", "5")
        ),
        retrieval_max_sources=int(
            os.getenv("RETRIEVAL_MAX_SOURCES", "5")
        ),
        text_chunking_enabled=get_boolean_setting(
            "TEXT_CHUNKING_ENABLED",
            True,
        ),
        text_chunk_size=int(
            os.getenv("TEXT_CHUNK_SIZE", "4000")
        ),
        text_chunk_overlap=int(
            os.getenv("TEXT_CHUNK_OVERLAP", "400")
        ),
        source_context_max_chunks=int(
            os.getenv("SOURCE_CONTEXT_MAX_CHUNKS", "3")
        ),
        source_context_max_characters=int(
            os.getenv("SOURCE_CONTEXT_MAX_CHARACTERS", "10000")
        ),
        report_target_word_count=int(
            os.getenv("REPORT_TARGET_WORD_COUNT", "3000")
        ),
        report_min_word_count=int(
            os.getenv("REPORT_MIN_WORD_COUNT", "2500")
        ),
        report_max_word_count=int(
            os.getenv("REPORT_MAX_WORD_COUNT", "3500")
        ),
    ),
    report_output_directory=os.getenv(
        "REPORT_OUTPUT_DIRECTORY",
        "reports",
    ),
    
)