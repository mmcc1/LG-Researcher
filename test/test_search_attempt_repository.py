from persistence.database import (
    SessionLocal,
)

from persistence.search_attempt_repository import (
    SearchAttemptRepository,
)


SESSION_ID = (
    "076c529a-365a-43ec-81ff-bb3780d195b1"
)

QUESTION_ID = 95


print()
print(
    "SEARCH ATTEMPT REPOSITORY TEST"
)
print(
    "=============================="
)


#
# Create.
#

with SessionLocal() as db:

    repository = (
        SearchAttemptRepository(db)
    )

    attempt = repository.create(
        session_id=SESSION_ID,
        question_id=QUESTION_ID,
        purpose="initial",
    )

    attempt_id = attempt.id

    print()
    print(
        f"Created attempt: {attempt_id}"
    )

    print(
        f"Purpose: {attempt.purpose}"
    )

    print(
        f"Status: {attempt.status}"
    )

    assert (
        attempt.status
        == "pending"
    )

    assert (
        attempt.completed_at
        is None
    )


#
# Verify pending lookup.
#

with SessionLocal() as db:

    repository = (
        SearchAttemptRepository(db)
    )

    pending = (
        repository.get_pending_for_question(
            QUESTION_ID
        )
    )

    assert pending is not None

    assert (
        pending.id
        == attempt_id
    )

    print()
    print(
        "Pending attempt found."
    )


#
# Mark running.
#

with SessionLocal() as db:

    repository = (
        SearchAttemptRepository(db)
    )

    repository.mark_running(
        attempt_id
    )

    attempt = repository.get(
        attempt_id
    )

    assert attempt is not None

    assert (
        attempt.status
        == "running"
    )

    assert (
        attempt.completed_at
        is None
    )

    print()
    print(
        "Attempt marked running."
    )


#
# Verify active lookup finds the
# running attempt.
#

with SessionLocal() as db:

    repository = (
        SearchAttemptRepository(db)
    )

    active = (
        repository.get_active_for_question(
            QUESTION_ID
        )
    )

    assert active is not None

    assert (
        active.id
        == attempt_id
    )

    assert (
        active.status
        == "running"
    )


#
# Mark completed.
#

with SessionLocal() as db:

    repository = (
        SearchAttemptRepository(db)
    )

    repository.mark_completed(
        attempt_id
    )

    attempt = repository.get(
        attempt_id
    )

    assert attempt is not None

    assert (
        attempt.status
        == "completed"
    )

    assert (
        attempt.completed_at
        is not None
    )

    print()
    print(
        "Attempt marked completed."
    )


#
# Completed attempts must no longer
# appear as pending or active.
#

with SessionLocal() as db:

    repository = (
        SearchAttemptRepository(db)
    )

    pending = (
        repository.get_pending_for_question(
            QUESTION_ID
        )
    )

    active = (
        repository.get_active_for_question(
            QUESTION_ID
        )
    )

    assert pending is None
    assert active is None


#
# Verify history.
#

with SessionLocal() as db:

    repository = (
        SearchAttemptRepository(db)
    )

    attempts = (
        repository.get_for_question(
            QUESTION_ID
        )
    )

    assert any(
        item.id == attempt_id
        for item in attempts
    )

    print()
    print(
        f"Attempt history count: "
        f"{len(attempts)}"
    )


print()
print(
    "PASS: search attempt lifecycle "
    "persisted correctly."
)