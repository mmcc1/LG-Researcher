
import {
    clearCsrfToken,
    request,
    setCsrfToken,
} from "./client";


export interface AuthenticatedUser {

    id: string;
    username: string;
    role: string;
    must_change_password: boolean;
}


export interface AuthSession {

    user: AuthenticatedUser;
    csrf_token: string;
    expires_at: string;
}


export async function login(
    username: string,
    password: string,
): Promise<AuthenticatedUser> {

    const session = await request<AuthSession>(
        "/api/auth/login",
        {
            method: "POST",
            body: JSON.stringify({
                username,
                password,
            }),
        },
    );

    setCsrfToken(
        session.csrf_token
    );

    return session.user;
}


export async function getCurrentSession():
    Promise<AuthenticatedUser> {

    const session = await request<AuthSession>(
        "/api/auth/me"
    );

    setCsrfToken(
        session.csrf_token
    );

    return session.user;
}


export async function logout(): Promise<void> {

    try {

        await request<void>(
            "/api/auth/logout",
            {
                method: "POST",
            },
        );

    } finally {

        clearCsrfToken();
    }
}


export async function changePassword(
    currentPassword: string,
    newPassword: string,
): Promise<void> {

    await request<{ message: string }>(
        "/api/auth/change-password",
        {
            method: "POST",
            body: JSON.stringify({
                current_password: currentPassword,
                new_password: newPassword,
            }),
        },
    );

    clearCsrfToken();
}
