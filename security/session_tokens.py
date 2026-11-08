
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
