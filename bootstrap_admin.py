
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select

from persistence.database import SessionLocal

from persistence.models import UserAccount

from security.password_hasher import hash_password


def main():

    print("Checking administrator account...")

    with SessionLocal.begin() as db:

        administrator = db.scalar(
            select(UserAccount).where(
                UserAccount.username == "admin"
            )
        )

        if administrator is not None:

            print(
                "An account named 'admin' already exists. "
                "No changes were made."
            )

            return

        now = datetime.now(
            timezone.utc
        ).replace(
            tzinfo=None
        )

        administrator = UserAccount(
            id=str(uuid4()),
            username="admin",
            email="admin@localhost.invalid",
            password_hash=hash_password("admin"),
            is_active=True,
            role="admin",
            approval_status="approved",
            must_change_password=True,
            approved_at=now,
            email_reports_enabled=False,
            created_at=now,
            last_login_at=None,
        )

        db.add(administrator)

    print("Administrator account created.")
    print("Username: admin")
    print(
        "The administrator must change "
        "the initial password at first login."
    )


if __name__ == "__main__":
    main()
