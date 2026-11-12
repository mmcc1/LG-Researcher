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

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)

from sqlalchemy import (
    func,
    select,
)

from sqlalchemy.orm import Session

from api.dependencies import (
    get_current_user_id,
    get_db,
)

from api.schemas.research_jobs import (
    AddResearchQuestionRequest,
    AddResearchQuestionResponse,
    CreateResearchJobRequest,
    ResearchJobActionResponse,
    ResearchJobResponse,
    ResearchQuestionResponse,
    ResearchJobListItemResponse,
    ResearchJobListResponse,
    UpdateResearchJobRequest,
)

from persistence.models import (
    ResearchJob,
    ResearchJobQuestion,
)

from persistence.research_job_repository import (
    ResearchJobRepository,
)


router = APIRouter(
    prefix="/api/research/jobs",
    tags=["Research Jobs"],
)


def get_owned_job(
    db: Session,
    job_id: str,
    user_id: str,
) -> ResearchJob:

    statement = (
        select(ResearchJob)
        .where(
            ResearchJob.id == job_id,
            ResearchJob.user_id == user_id,
        )
    )

    job = db.execute(
        statement
    ).scalar_one_or_none()

    if job is None:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research job not found.",
        )

    return job


def build_job_response(
    db: Session,
    job: ResearchJob,
) -> ResearchJobResponse:

    statement = (
        select(ResearchJobQuestion)
        .where(
            ResearchJobQuestion.research_job_id
            == job.id
        )
        .order_by(
            ResearchJobQuestion.id
        )
    )

    questions = db.execute(
        statement
    ).scalars().all()

    question_responses = []

    for question in questions:

        question_response = (
            ResearchQuestionResponse(
                id=question.id,
                question=question.question,
                created_at=question.created_at,
            )
        )

        question_responses.append(
            question_response
        )

    return ResearchJobResponse(
        id=job.id,
        topic=job.topic,
        scope=job.scope,
        status=job.status,
        research_session_id=(
            job.research_session_id
        ),
        created_at=job.created_at,
        submitted_at=job.submitted_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        questions=question_responses,
    )


@router.post(
    "",
    response_model=ResearchJobResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_research_job(
    request: CreateResearchJobRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):

    topic = request.topic.strip()

    if not topic:

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Research topic cannot be empty.",
        )

    repository = ResearchJobRepository(
        db
    )

    job_id = repository.create_draft(
        user_id=user_id,
        topic=topic,
        scope=request.scope,
    )

    job = get_owned_job(
        db=db,
        job_id=job_id,
        user_id=user_id,
    )

    return build_job_response(
        db=db,
        job=job,
    )



@router.patch(
    "/{job_id}",
    response_model=ResearchJobResponse,
)
def update_research_job(
    job_id: str,
    request: UpdateResearchJobRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):

    get_owned_job(
        db=db,
        job_id=job_id,
        user_id=user_id,
    )

    topic = request.topic.strip()

    if not topic:

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Research topic cannot be empty.",
        )

    repository = ResearchJobRepository(
        db
    )

    updated = repository.update_draft(
        job_id=job_id,
        user_id=user_id,
        topic=topic,
        scope=request.scope,
    )

    if not updated:

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Only draft research jobs "
                "can be updated."
            ),
        )

    # update_draft() commits its transaction.
    # Re-read the job to return its persisted values.

    db.expire_all()

    job = get_owned_job(
        db=db,
        job_id=job_id,
        user_id=user_id,
    )

    return build_job_response(
        db=db,
        job=job,
    )


@router.post(
    "/{job_id}/questions",
    response_model=AddResearchQuestionResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_research_question(
    job_id: str,
    request: AddResearchQuestionRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):

    get_owned_job(
        db=db,
        job_id=job_id,
        user_id=user_id,
    )

    question = request.question.strip()

    if not question:

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Research question cannot be empty.",
        )

    repository = ResearchJobRepository(
        db
    )

    question_id = repository.add_draft_question(
        job_id=job_id,
        user_id=user_id,
        question=question,
    )

    if question_id is None:

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Questions can only be added "
                "to a draft research job."
            ),
        )

    return AddResearchQuestionResponse(
        id=question_id,
        research_job_id=job_id,
        question=question,
    )


@router.delete(
    "/{job_id}/questions/{question_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_research_question(
    job_id: str,
    question_id: int,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):

    get_owned_job(
        db=db,
        job_id=job_id,
        user_id=user_id,
    )

    repository = ResearchJobRepository(
        db
    )

    removed = repository.remove_draft_question(
        job_id=job_id,
        user_id=user_id,
        question_id=question_id,
    )

    if not removed:

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The question could not be removed. "
                "The job must be a draft and "
                "the question must belong to it."
            ),
        )

    return None


@router.post(
    "/{job_id}/submit",
    response_model=ResearchJobActionResponse,
)
def submit_research_job(
    job_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):

    get_owned_job(
        db=db,
        job_id=job_id,
        user_id=user_id,
    )

    repository = ResearchJobRepository(
        db
    )

    submitted = repository.submit_draft(
        job_id=job_id,
        user_id=user_id,
    )

    if not submitted:

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The research job cannot be submitted "
                "from its current state."
            ),
        )

    return ResearchJobActionResponse(
        id=job_id,
        status="queued",
    )


@router.post(
    "/{job_id}/pause",
    response_model=ResearchJobActionResponse,
)
def pause_research_job(
    job_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):

    get_owned_job(
        db=db,
        job_id=job_id,
        user_id=user_id,
    )

    repository = ResearchJobRepository(
        db
    )

    try:

        result = repository.request_pause(
            job_id=job_id,
            user_id=user_id,
        )

    except RuntimeError as exc:

        if str(exc) != (
            "Research job is being initialised. "
            "Retry the pause request shortly."
        ):
            raise

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    if result is None:

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The research job cannot be paused "
                "from its current state."
            ),
        )

    return ResearchJobActionResponse(
        id=job_id,
        status=result,
    )


@router.post(
    "/{job_id}/resume",
    response_model=ResearchJobActionResponse,
)
def resume_research_job(
    job_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):

    get_owned_job(
        db=db,
        job_id=job_id,
        user_id=user_id,
    )

    repository = ResearchJobRepository(
        db
    )

    resumed = repository.resume_paused(
        job_id=job_id,
        user_id=user_id,
    )

    if not resumed:

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The research job cannot be resumed "
                "from its current state."
            ),
        )

    return ResearchJobActionResponse(
        id=job_id,
        status="queued",
    )

@router.get(
    "",
    response_model=ResearchJobListResponse,
)
def list_research_jobs(
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):

    count_statement = (
        select(
            func.count()
        )
        .select_from(
            ResearchJob
        )
        .where(
            ResearchJob.user_id == user_id
        )
    )

    total = db.execute(
        count_statement
    ).scalar_one()

    statement = (
        select(ResearchJob)
        .where(
            ResearchJob.user_id == user_id
        )
        .order_by(
            ResearchJob.created_at.desc(),
            ResearchJob.id.desc(),
        )
        .offset(
            offset
        )
        .limit(
            limit
        )
    )

    jobs = db.execute(
        statement
    ).scalars().all()

    items = []

    for job in jobs:

        item = ResearchJobListItemResponse(
            id=job.id,
            topic=job.topic,
            scope=job.scope,
            status=job.status,
            research_session_id=(
                job.research_session_id
            ),
            created_at=job.created_at,
            submitted_at=job.submitted_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
        )

        items.append(
            item
        )

    return ResearchJobListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{job_id}",
    response_model=ResearchJobResponse,
)
def get_research_job(
    job_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):

    job = get_owned_job(
        db=db,
        job_id=job_id,
        user_id=user_id,
    )

    return build_job_response(
        db=db,
        job=job,
    )
