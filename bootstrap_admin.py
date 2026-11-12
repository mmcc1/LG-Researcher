
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
