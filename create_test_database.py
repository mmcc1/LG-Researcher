
from sqlalchemy import create_engine

from persistence.database import Base, engine
from persistence import models


def main():

    test_url = engine.url.set(
        database="LGResearcher_Test"
    )

    test_engine = create_engine(
        test_url,
        echo=False,
    )

    try:

        print("Creating test database tables...")

        Base.metadata.create_all(
            bind=test_engine
        )

        print("Done.")

    finally:

        test_engine.dispose()


if __name__ == "__main__":
    main()
