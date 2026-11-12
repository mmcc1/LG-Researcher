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

import hashlib
import hmac
import secrets


def generate_token() -> str:

    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:

    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def verify_token(
    supplied_token: str,
    expected_hash: str,
) -> bool:

    supplied_hash = hash_token(
        supplied_token
    )

    return hmac.compare_digest(
        supplied_hash,
        expected_hash,
    )
