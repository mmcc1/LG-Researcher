from persistence.database import Base, engine
from persistence import models


def main():
    print("Creating database tables...")

    Base.metadata.create_all(bind=engine)

    print("Done.")


if __name__ == "__main__":
    main()