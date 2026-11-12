#     LGResearcher - A Langgraph-based LLM agnostic research engine
#     Copyright (C) 2026  Mark McCarron

#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.

#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.

#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <https://www.gnu.org/licenses/>

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
    pool_pre_ping=True,
    pool_recycle=1800,
)


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)