from persistence.database import (
    SessionLocal,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)


print()
print("PAUSE REPOSITORY TEST")
print("=====================")


#
# -------------------------------------------------
# Create session.
# -------------------------------------------------
#

with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    research_session = (
        repository.create(
            topic="Pause repository test",
        )
    )

    session_id = (
        research_session.id
    )


print(
    f"Session ID: {session_id}"
)


#
# -------------------------------------------------
# TEST 1
#
# No pause initially.
# -------------------------------------------------
#

print()
print("TEST 1 - INITIAL STATE")
print("----------------------")


with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    assert (
        repository.is_pause_requested(
            session_id
        )
        is False
    )


print(
    "Initial pause state: PASSED"
)


#
# -------------------------------------------------
# TEST 2
#
# Request pause.
# -------------------------------------------------
#

print()
print("TEST 2 - REQUEST PAUSE")
print("----------------------")


with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    research_session = (
        repository.request_pause(
            session_id
        )
    )

    assert (
        research_session.pause_requested
        is True
    )


print(
    "Pause requested: PASSED"
)


#
# -------------------------------------------------
# TEST 3
#
# Verify request survives a new SQL session.
# -------------------------------------------------
#

print()
print("TEST 3 - DURABLE PAUSE REQUEST")
print("------------------------------")


with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    assert (
        repository.is_pause_requested(
            session_id
        )
        is True
    )


print(
    "Durable pause request: PASSED"
)


#
# -------------------------------------------------
# TEST 4
#
# Clear pause.
# -------------------------------------------------
#

print()
print("TEST 4 - CLEAR PAUSE REQUEST")
print("----------------------------")


with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    research_session = (
        repository.clear_pause_request(
            session_id
        )
    )

    assert (
        research_session.pause_requested
        is False
    )


print(
    "Pause request cleared: PASSED"
)


#
# -------------------------------------------------
# TEST 5
#
# Verify clear survives a new SQL session.
# -------------------------------------------------
#

print()
print("TEST 5 - DURABLE CLEAR")
print("----------------------")


with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    assert (
        repository.is_pause_requested(
            session_id
        )
        is False
    )


print(
    "Durable clear: PASSED"
)


#
# -------------------------------------------------
# TEST 6
#
# Missing sessions fail closed.
# -------------------------------------------------
#

print()
print("TEST 6 - MISSING SESSION")
print("------------------------")


missing_session_id = (
    "00000000-0000-0000-0000-000000000000"
)


operations = [
    (
        "is_pause_requested",
        lambda repository: (
            repository.is_pause_requested(
                missing_session_id
            )
        ),
    ),
    (
        "request_pause",
        lambda repository: (
            repository.request_pause(
                missing_session_id
            )
        ),
    ),
    (
        "clear_pause_request",
        lambda repository: (
            repository.clear_pause_request(
                missing_session_id
            )
        ),
    ),
]


for name, operation in operations:

    with SessionLocal() as db:

        repository = (
            ResearchSessionRepository(db)
        )

        try:

            operation(
                repository
            )

            raise AssertionError(
                f"{name} should have failed."
            )

        except ValueError:

            print(
                f"{name}: PASSED"
            )


print()
print("=====================")
print("PASS")
print("=====================")

print(
    "Pause request persistence primitives "
    "work correctly."
)