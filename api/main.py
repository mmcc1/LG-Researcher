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

from fastapi import FastAPI

from api.routes.research_jobs import (
    router as research_jobs_router,
)

from api.routes.auth import (
    router as auth_router,
)

from api.routes.admin import (
    router as admin_router,
)

app = FastAPI(
    title="LG Researcher API",
    description=(
        "HTTP API for managing research jobs "
        "and retrieving research results."
    ),
    version="0.1.0",
)

app.include_router(
    auth_router
)

app.include_router(
    research_jobs_router
)

app.include_router(
    admin_router
)


@app.get(
    "/api/health",
    tags=["Health"],
)
def health():

    return {
        "status": "ok",
    }
