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

import json
import os
import math

from pathlib import Path
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Response,
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

from persistence.models import (
    AdminAuditLog,
    ResearchJob,
    UserAccount,
    UserSession,
    PasswordResetRequest,
)

from api.schemas.admin import (
    AdminActionResponse,
    AdminResearchJobListResponse,
    AdminResearchJobResponse,
    AdminResearchJobStatusCount,
    AdminResearchJobSummaryResponse,
    AdminUserListResponse,
    AdminUserResponse,
    AdminPasswordResetActionResponse,
    AdminPasswordResetApprovalResponse,
    AdminPasswordResetRequestListResponse,
    AdminPasswordResetRequestResponse,
)

from sqlalchemy import (
    false,
    func,
    select,
    true,
    update,
)

from application.authentication_service import (
    AuthenticationService,
    PasswordResetError,
    utc_now,
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


def build_password_reset_response(
    reset_request: PasswordResetRequest,
    username: str,
) -> AdminPasswordResetRequestResponse:

    return AdminPasswordResetRequestResponse(
        id=reset_request.id,
        user_id=reset_request.user_id,
        username=username,
        status=reset_request.status,
        requested_at=reset_request.requested_at,
        reviewed_at=reset_request.reviewed_at,
        reviewed_by=reset_request.reviewed_by,
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



@router.post(
    "/users/{user_id}/enable",
    response_model=AdminActionResponse,
)
def enable_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
):

    result = db.execute(
        update(UserAccount)
        .where(
            UserAccount.id == user_id,
            UserAccount.role == "user",
            UserAccount.approval_status == "approved",
            UserAccount.is_active == false(),
        )
        .values(
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
                "User not found, not approved, "
                "or already enabled."
            ),
        )

    record_admin_action(
        db=db,
        actor_user_id=admin.id,
        action="user.enabled",
        target_user_id=user_id,
        details={
            "is_active": True,
        },
    )

    db.commit()

    return AdminActionResponse(
        id=user_id,
        approval_status="approved",
        message="User enabled successfully.",
    )


@router.post(
    "/users/{user_id}/disable",
    response_model=AdminActionResponse,
)
def disable_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
):

    if user_id == admin.id:

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Administrators cannot disable "
                "their own accounts."
            ),
        )

    now = utc_now()

    result = db.execute(
        update(UserAccount)
        .where(
            UserAccount.id == user_id,
            UserAccount.role == "user",
            UserAccount.approval_status == "approved",
            UserAccount.is_active == true(),
        )
        .values(
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
                "User not found, not approved, "
                "or already disabled."
            ),
        )

    db.execute(
        update(UserSession)
        .where(
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
        )
        .values(
            revoked_at=now,
        )
        .execution_options(
            synchronize_session=False
        )
    )

    record_admin_action(
        db=db,
        actor_user_id=admin.id,
        action="user.disabled",
        target_user_id=user_id,
        details={
            "is_active": False,
            "sessions_revoked": True,
        },
    )

    db.commit()

    return AdminActionResponse(
        id=user_id,
        approval_status="approved",
        message=(
            "User disabled successfully. "
            "Existing sessions have been revoked."
        ),
    )


@router.get(
    "/password-reset-requests",
    response_model=AdminPasswordResetRequestListResponse,
)
def list_password_reset_requests(
    reset_status: str | None = Query(
        default=None,
        alias="status",
        pattern="^(pending|completed|rejected)$",
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

    if reset_status is not None:

        filters.append(
            PasswordResetRequest.status == reset_status
        )

    count_statement = (
        select(func.count())
        .select_from(PasswordResetRequest)
        .where(*filters)
    )

    total = db.execute(
        count_statement
    ).scalar_one()

    statement = (
        select(
            PasswordResetRequest,
            UserAccount.username,
        )
        .join(
            UserAccount,
            PasswordResetRequest.user_id == UserAccount.id,
        )
        .where(*filters)
        .order_by(
            PasswordResetRequest.requested_at.desc(),
            PasswordResetRequest.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )

    results = db.execute(
        statement
    ).all()

    items = []

    for reset_request, username in results:

        item = build_password_reset_response(
            reset_request=reset_request,
            username=username,
        )

        items.append(item)

    return AdminPasswordResetRequestListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/password-reset-requests/{request_id}/approve",
    response_model=AdminPasswordResetApprovalResponse,
)
def approve_password_reset_request(
    request_id: str,
    response: Response,
    db: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
):

    reset_request = db.get(
        PasswordResetRequest,
        request_id,
    )

    if reset_request is None:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Password reset request not found.",
        )

    if reset_request.user_id == admin.id:

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Administrators cannot approve "
                "their own password resets."
            ),
        )

    service = AuthenticationService(
        db
    )

    try:

        temporary_password = (
            service.approve_password_reset(
                reset_request=reset_request,
                admin=admin,
            )
        )

        record_admin_action(
            db=db,
            actor_user_id=admin.id,
            action="password_reset.approved",
            target_user_id=reset_request.user_id,
            details={
                "request_id": reset_request.id,
                "sessions_revoked": True,
                "must_change_password": True,
            },
        )

        db.commit()

    except PasswordResetError as exc:

        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    except Exception:

        db.rollback()

        raise

    response.headers["Cache-Control"] = (
        "no-store"
    )

    response.headers["Pragma"] = (
        "no-cache"
    )

    return AdminPasswordResetApprovalResponse(
        id=request_id,
        status="completed",
        message=(
            "Password reset approved. "
            "Provide the temporary password "
            "to the verified account owner."
        ),
        temporary_password=temporary_password,
    )


@router.post(
    "/password-reset-requests/{request_id}/reject",
    response_model=AdminPasswordResetActionResponse,
)
def reject_password_reset_request(
    request_id: str,
    db: Session = Depends(get_db),
    admin: UserAccount = Depends(require_admin),
):

    reset_request = db.get(
        PasswordResetRequest,
        request_id,
    )

    if reset_request is None:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Password reset request not found.",
        )

    service = AuthenticationService(
        db
    )

    try:

        service.reject_password_reset(
            reset_request=reset_request,
            admin=admin,
        )

        record_admin_action(
            db=db,
            actor_user_id=admin.id,
            action="password_reset.rejected",
            target_user_id=reset_request.user_id,
            details={
                "request_id": reset_request.id,
            },
        )

        db.commit()

    except PasswordResetError as exc:

        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    except Exception:

        db.rollback()

        raise

    return AdminPasswordResetActionResponse(
        id=request_id,
        status="rejected",
        message="Password reset request rejected.",
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


def validate_recovery_health_snapshot(
    snapshot: object,
) -> dict:

    if not isinstance(snapshot, dict):

        raise ValueError(
            "Recovery health snapshot must be a JSON object."
        )

    required_fields = {
        "state": str,
        "pid": int,
        "started_at": str,
        "updated_at": str,
        "cycles": int,
        "resumed": int,
        "paused": int,
        "skipped": int,
        "failed_sessions": int,
        "cycle_errors": int,
    }

    for field_name, expected_type in required_fields.items():

        value = snapshot.get(
            field_name
        )

        if type(value) is not expected_type:

            raise ValueError(
                f"Invalid recovery health field: {field_name}"
            )

    allowed_states = {
        "starting",
        "running",
        "recovering",
        "stopping",
        "stopped",
    }

    if snapshot["state"] not in allowed_states:

        raise ValueError(
            "Invalid recovery health state."
        )

    for field_name in (
        "last_cycle_at",
        "last_success_at",
        "last_error",
    ):

        value = snapshot.get(
            field_name
        )

        if (
            value is not None
            and not isinstance(value, str)
        ):

            raise ValueError(
                f"Invalid recovery health field: {field_name}"
            )

    duration = snapshot.get(
        "last_cycle_duration_seconds"
    )

    if (
        duration is not None
        and (
            type(duration) not in (int, float)
            or not math.isfinite(duration)
            or duration < 0
        )
    ):

        raise ValueError(
            "Invalid recovery cycle duration."
        )

    return snapshot


@router.get(
    "/recovery/health",
)
def get_admin_recovery_health(
    admin: UserAccount = Depends(require_admin),
):

    configured_path = os.environ.get(
        "RESEARCH_RECOVERY_HEALTH_FILE"
    )

    if (
        configured_path is None
        or not configured_path.strip()
    ):

        return {
            "available": False,
            "health": None,
        }

    health_path = Path(
        configured_path.strip()
    )

    try:

        with health_path.open(
            "r",
            encoding="utf-8",
        ) as health_file:

            snapshot = json.load(
                health_file
            )

    except FileNotFoundError:

        return {
            "available": False,
            "health": None,
        }

    except (OSError, UnicodeError, ValueError):

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Recovery health snapshot is unavailable.",
        )

    try:

        validated_snapshot = (
            validate_recovery_health_snapshot(
                snapshot
            )
        )

    except ValueError:

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Recovery health snapshot is invalid.",
        )

    return {
        "available": True,
        "health": validated_snapshot,
    }
