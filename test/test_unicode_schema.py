
from sqlalchemy import inspect
from sqlalchemy import Unicode
from sqlalchemy import UnicodeText

from persistence.database import (
    Base,
    SessionLocal,
)

import persistence.models


def main():

    print()
    print("UNICODE SCHEMA VALIDATION")
    print("=========================")
    print()

    with SessionLocal() as db:

        connection = db.connection()

        inspector = inspect(
            connection
        )

        checked_columns = 0

        for table in Base.metadata.sorted_tables:

            database_columns = {
                column["name"]: column
                for column in inspector.get_columns(
                    table.name,
                    schema="dbo",
                )
            }

            for column in table.columns:

                if not isinstance(
                    column.type,
                    (Unicode, UnicodeText),
                ):

                    continue

                database_column = database_columns[
                    column.name
                ]

                database_type = str(
                    database_column["type"]
                ).upper()

                assert database_type.startswith(
                    ("NVARCHAR", "NTEXT", "NCHAR")
                ), (
                    f"{table.name}.{column.name}: "
                    f"expected Unicode storage, "
                    f"found {database_type}"
                )

                checked_columns += 1

                print(
                    f"{table.name}.{column.name}: "
                    "PASSED"
                )

        print()
        print(
            "Unicode columns verified: "
            f"{checked_columns}"
        )

        print()
        print(
            "Unicode schema validation: PASSED"
        )


if __name__ == "__main__":
    main()
