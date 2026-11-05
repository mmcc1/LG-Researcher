from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import settings


class Base(DeclarativeBase):
    pass


connection_url = URL.create(
    "mssql+pyodbc",
    username=settings.database.username,
    password=settings.database.password,
    host=settings.database.server,
    port=settings.database.port,
    database=settings.database.database,
    query={
        "driver": settings.database.driver,
        "TrustServerCertificate":
            settings.database.trust_server_certificate,
    },
)


engine = create_engine(
    connection_url,
    echo=False,
)


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)