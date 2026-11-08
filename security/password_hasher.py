
from argon2 import PasswordHasher
from argon2.exceptions import (
    InvalidHashError,
    VerifyMismatchError,
    VerificationError,
)


_hasher = PasswordHasher()


def hash_password(password: str) -> str:

    return _hasher.hash(password)


def verify_password(
    password: str,
    password_hash: str,
) -> bool:

    try:

        return _hasher.verify(
            password_hash,
            password,
        )

    except (
        InvalidHashError,
        VerifyMismatchError,
        VerificationError,
    ):

        return False


def password_needs_rehash(
    password_hash: str,
) -> bool:

    return _hasher.check_needs_rehash(
        password_hash
    )
