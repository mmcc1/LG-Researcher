
import argparse

from sqlalchemy import text

from persistence.database import (
    Base,
    engine,
)

from persistence.models import (
    AdminAuditLog,
    PasswordResetRequest,
    UserSession,
)


def quote_identifier(value: str) -> str:

    return "[" + value.replace("]", "]]") + "]"


def migrate_email_column(connection):

    column = connection.execute(
        text(
            """
            SELECT c.is_nullable
            FROM sys.columns AS c
            WHERE c.object_id = OBJECT_ID('dbo.users')
              AND c.name = 'email'
            """
        )
    ).mappings().first()

    if column is None:

        raise RuntimeError(
            "The dbo.users.email column was not found."
        )

    indexes = connection.execute(
        text(
            """
            SELECT
                i.name AS index_name,
                i.is_unique,
                i.is_primary_key,
                kc.name AS constraint_name,
                COUNT(*) AS column_count,
                MAX(
                    CASE
                        WHEN c.name = 'email'
                        THEN 1
                        ELSE 0
                    END
                ) AS includes_email
            FROM sys.indexes AS i
            JOIN sys.index_columns AS ic
                ON ic.object_id = i.object_id
               AND ic.index_id = i.index_id
            JOIN sys.columns AS c
                ON c.object_id = ic.object_id
               AND c.column_id = ic.column_id
            LEFT JOIN sys.key_constraints AS kc
                ON kc.parent_object_id = i.object_id
               AND kc.unique_index_id = i.index_id
            WHERE i.object_id = OBJECT_ID('dbo.users')
              AND ic.key_ordinal > 0
            GROUP BY
                i.name,
                i.is_unique,
                i.is_primary_key,
                kc.name
            """
        )
    ).mappings().all()

    for index in indexes:

        if not index["includes_email"]:

            continue

        if index["column_count"] != 1:

            raise RuntimeError(
                "Email participates in a composite index: "
                + str(index["index_name"])
                + ". Review this index before migrating."
            )

        if index["is_primary_key"]:

            raise RuntimeError(
                "Unexpected primary key on email."
            )

        if index["constraint_name"]:

            name = quote_identifier(
                index["constraint_name"]
            )

            connection.execute(
                text(
                    f"ALTER TABLE dbo.users "
                    f"DROP CONSTRAINT {name}"
                )
            )

        else:

            name = quote_identifier(
                index["index_name"]
            )

            connection.execute(
                text(
                    f"DROP INDEX {name} ON dbo.users"
                )
            )

    if not column["is_nullable"]:

        connection.execute(
            text(
                """
                ALTER TABLE dbo.users
                ALTER COLUMN email VARCHAR(320) NULL
                """
            )
        )

    connection.execute(
        text(
            """
            IF NOT EXISTS (
                SELECT 1
                FROM sys.indexes
                WHERE object_id = OBJECT_ID('dbo.users')
                  AND name = 'ux_users_email_not_null'
            )
            BEGIN
                CREATE UNIQUE INDEX ux_users_email_not_null
                ON dbo.users(email)
                WHERE email IS NOT NULL;
            END
            """
        )
    )


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--expect-database",
        required=True,
        help="Database name that must match the connection.",
    )

    args = parser.parse_args()

    with engine.begin() as connection:

        database_name = connection.scalar(
            text("SELECT DB_NAME()")
        )

        if (
            database_name.casefold()
            != args.expect_database.casefold()
        ):

            raise RuntimeError(
                "Database mismatch. Connected to "
                f"'{database_name}', expected "
                f"'{args.expect_database}'."
            )

        print(
            f"Migrating database: {database_name}"
        )

        migrate_email_column(connection)

        Base.metadata.create_all(
            bind=connection,
            tables=[
                UserSession.__table__,
                PasswordResetRequest.__table__,
                AdminAuditLog.__table__,
            ],
            checkfirst=True,
        )

    print("Authentication migration complete.")


if __name__ == "__main__":
    main()
