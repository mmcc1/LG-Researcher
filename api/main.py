
from fastapi import FastAPI

from api.routes.research_jobs import (
    router as research_jobs_router,
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
    research_jobs_router
)


@app.get(
    "/api/health",
    tags=["Health"],
)
def health():

    return {
        "status": "ok",
    }
