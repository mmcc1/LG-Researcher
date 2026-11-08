
from sqlalchemy import text

from persistence.database import engine


def main():

    print("Migrating user accounts...")

    with engine.begin() as connection:

        connection.execute(
            text(
                """
                IF COL_LENGTH(
                    'dbo.users',
                    'role'
                ) IS NULL
                BEGIN
                    ALTER TABLE dbo.users
                    ADD role VARCHAR(20)
                        NOT NULL
                        CONSTRAINT DF_users_role
                        DEFAULT 'user';
                END
                """
            )
        )

        connection.execute(
            text(
                """
                IF COL_LENGTH(
                    'dbo.users',
                    'approval_status'
                ) IS NULL
                BEGIN
                    ALTER TABLE dbo.users
                    ADD approval_status VARCHAR(20)
                        NOT NULL
                        CONSTRAINT DF_users_approval_status
                        DEFAULT 'approved';
                END
                """
            )
        )

        connection.execute(
            text(
                """
                IF COL_LENGTH(
                    'dbo.users',
                    'must_change_password'
                ) IS NULL
                BEGIN
                    ALTER TABLE dbo.users
                    ADD must_change_password BIT
                        NOT NULL
                        CONSTRAINT DF_users_must_change_password
                        DEFAULT 0;
                END
                """
            )
        )

        connection.execute(
            text(
                """
                IF COL_LENGTH(
                    'dbo.users',
                    'approved_at'
                ) IS NULL
                BEGIN
                    ALTER TABLE dbo.users
                    ADD approved_at DATETIME NULL;
                END
                """
            )
        )

    print("User account migration complete.")


if __name__ == "__main__":
    main()
