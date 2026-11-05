import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class ModelSettings:
    provider: str
    model_name: str
    base_url: str
    temperature: float


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
class Settings:
    planner_model: ModelSettings
    researcher_model: ModelSettings
    summariser_model: ModelSettings
    reviewer_model: ModelSettings
    reporter_model: ModelSettings
    controller_model: ModelSettings

    database: DatabaseSettings


def create_model_settings(
    prefix: str,
) -> ModelSettings:

    return ModelSettings(
        provider=os.getenv(
            f"{prefix}_PROVIDER",
            "ollama",
        ),
        model_name=os.getenv(
            f"{prefix}_MODEL",
            "qwen3:8b",
        ),
        base_url=os.getenv(
            f"{prefix}_BASE_URL",
            "http://localhost:11434",
        ),
        temperature=float(
            os.getenv(
                f"{prefix}_TEMPERATURE",
                "0.2",
            )
        ),
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
)