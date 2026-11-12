
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
