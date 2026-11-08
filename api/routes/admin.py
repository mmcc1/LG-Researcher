
import json

from uuid import uuid4

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
    update,
)

from sqlalchemy.orm import Session

from api.dependencies import (
    get_db,
    require_admin,
)

from application.authentication_service import utc_now

from persistence.models import (
    AdminAuditLog,
    ResearchJob,
    UserAccount,
)

from api.schemas.admin import (
    AdminActionResponse,
    AdminResearchJobListResponse,
    AdminResearchJobResponse,
    AdminResearchJobStatusCount,
    AdminResearchJobSummaryResponse,
    AdminUserListResponse,
    AdminUserResponse,
)


router = APIRouter(
    prefix="/api/admin",
    tags=["Administration"],
)


def build_user_response(
    user: UserAccount,
) -> AdminUserResponse:

    return AdminUserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        approval_status=user.approval_status,
        must_change_password=user.must_change_password,
        created_at=user.created_at,
        approved_at=user.approved_at,
        last_login_at=user.last_login_at,
    )


def record_admin_action(
    db: Session,
    actor_user_id: str,
    action: str,
    target_user_id: str,
    details: dict,
) -> None:

    audit = AdminAuditLog(
        id=str(uuid4()),
        actor_user_id=actor_user_id,
        action=action,
        target_type="user",
        target_id=target_user_id,
        details=json.dumps(details),
        created_at=utc_now(),
    )

    db.add(audit)


@router.get(
    "/users",
    response_model=AdminUserListResponse,
)
def list_users(
    approval_status: str | None = Query(
        default=None,
        pattern="^(pending|approved|rejected)$",
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=100,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
    db: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
):

    filters = []

    if approval_status is not None:

        filters.append(
            UserAccount.approval_status
            == approval_status
        )

    count_statement = (
        select(func.count())
        .select_from(UserAccount)
        .where(*filters)
    )

    total = db.execute(
        count_statement
    ).scalar_one()

    statement = (
        select(UserAccount)
        .where(*filters)
        .order_by(
            UserAccount.created_at.desc(),
            UserAccount.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )

    users = db.execute(
        statement
    ).scalars().all()

    items = []

    for user in users:

        items.append(
            build_user_response(user)
        )

    return AdminUserListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/users/{user_id}/approve",
    response_model=AdminActionResponse,
)
def approve_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
):

    now = utc_now()

    result = db.execute(
        update(UserAccount)
        .where(
            UserAccount.id == user_id,
            UserAccount.approval_status == "pending",
            UserAccount.role == "user",
        )
        .values(
            approval_status="approved",
            approved_at=now,
            is_active=True,
        )
        .execution_options(
            synchronize_session=False
        )
    )

    if result.rowcount != 1:

        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "User not found or registration "
                "is no longer pending."
            ),
        )

    record_admin_action(
        db=db,
        actor_user_id=admin.id,
        action="user.approved",
        target_user_id=user_id,
        details={
            "approval_status": "approved",
        },
    )

    db.commit()

    return AdminActionResponse(
        id=user_id,
        approval_status="approved",
        message="User approved successfully.",
    )


@router.post(
    "/users/{user_id}/reject",
    response_model=AdminActionResponse,
)
def reject_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
):

    result = db.execute(
        update(UserAccount)
        .where(
            UserAccount.id == user_id,
            UserAccount.approval_status == "pending",
            UserAccount.role == "user",
        )
        .values(
            approval_status="rejected",
            is_active=False,
        )
        .execution_options(
            synchronize_session=False
        )
    )

    if result.rowcount != 1:

        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "User not found or registration "
                "is no longer pending."
            ),
        )

    record_admin_action(
        db=db,
        actor_user_id=admin.id,
        action="user.rejected",
        target_user_id=user_id,
        details={
            "approval_status": "rejected",
        },
    )

    db.commit()

    return AdminActionResponse(
        id=user_id,
        approval_status="rejected",
        message="Registration rejected.",
    )




@router.get(
    "/research/jobs",
    response_model=AdminResearchJobListResponse,
)
def list_admin_research_jobs(
    job_status: str | None = Query(
        default=None,
        min_length=1,
        max_length=50,
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=100,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
    db: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
):

    filters = []

    if job_status is not None:

        filters.append(
            ResearchJob.status == job_status
        )

    count_statement = (
        select(func.count())
        .select_from(ResearchJob)
        .where(*filters)
    )

    total = db.execute(
        count_statement
    ).scalar_one()

    statement = (
        select(
            ResearchJob,
            UserAccount.username,
        )
        .join(
            UserAccount,
            ResearchJob.user_id == UserAccount.id,
        )
        .where(*filters)
        .order_by(
            ResearchJob.created_at.desc(),
            ResearchJob.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )

    results = db.execute(
        statement
    ).all()

    items = []

    for job, username in results:

        item = AdminResearchJobResponse(
            id=job.id,
            user_id=job.user_id,
            username=username,
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
            last_error=job.last_error,
            execution_owner=job.execution_owner,
            lease_expires_at=job.lease_expires_at,
        )

        items.append(
            item
        )

    return AdminResearchJobListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/research/jobs/summary",
    response_model=AdminResearchJobSummaryResponse,
)
def get_admin_research_job_summary(
    db: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
):

    statement = (
        select(
            ResearchJob.status,
            func.count().label("job_count"),
        )
        .group_by(
            ResearchJob.status
        )
        .order_by(
            ResearchJob.status
        )
    )

    results = db.execute(
        statement
    ).all()

    statuses = []

    total = 0

    for job_status, count in results:

        statuses.append(
            AdminResearchJobStatusCount(
                status=job_status,
                count=count,
            )
        )

        total += count

    return AdminResearchJobSummaryResponse(
        total=total,
        statuses=statuses,
    )
