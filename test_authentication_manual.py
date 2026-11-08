
import requests


BASE_URL = "http://127.0.0.1:8000"


def main():

    client = requests.Session()

    client.headers.update({
        "Origin": BASE_URL,
    })

    print("Logging in...")

    response = client.post(
        f"{BASE_URL}/api/auth/login",
        json={
            "username": "admin",
            "password": "admin",
        },
        timeout=30,
    )

    response.raise_for_status()

    login_result = response.json()

    print(
        "Login response:",
        login_result["user"],
    )

    assert (
        login_result["user"][
            "must_change_password"
        ]
        is True
    )

    print("Checking restricted access...")

    response = client.get(
        f"{BASE_URL}/api/research/jobs",
        timeout=30,
    )

    assert response.status_code == 403

    print(
        "Research access correctly blocked."
    )

    print("Checking current session...")

    response = client.get(
        f"{BASE_URL}/api/auth/me",
        timeout=30,
    )

    response.raise_for_status()

    current_session = response.json()

    csrf_token = current_session[
        "csrf_token"
    ]

    print("Checking CSRF rejection...")

    response = client.post(
        f"{BASE_URL}/api/auth/logout",
        timeout=30,
    )

    assert response.status_code == 403

    print(
        "Missing CSRF token correctly rejected."
    )

    print("Logging out...")

    client.headers.update({
        "X-CSRF-Token": csrf_token,
    })

    response = client.post(
        f"{BASE_URL}/api/auth/logout",
        timeout=30,
    )

    assert response.status_code == 204

    print("Logout successful.")

    response = client.get(
        f"{BASE_URL}/api/auth/me",
        timeout=30,
    )

    assert response.status_code == 401

    print(
        "Revoked session correctly rejected."
    )

    print("Authentication smoke test passed.")


if __name__ == "__main__":
    main()
