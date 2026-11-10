
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


export interface RegistrationInput {

    username: string;
    password: string;
    confirm_password: string;
}


export interface RegistrationResponse {

    message: string;
}


export async function register(
    input: RegistrationInput,
): Promise<RegistrationResponse> {

    return await request<RegistrationResponse>(
        "/api/auth/register",
        {
            method: "POST",
            body: JSON.stringify(input),
        },
    );
}


export interface PasswordResetRequestResponse {

    message: string;
}


export async function requestPasswordReset(
    username: string,
): Promise<PasswordResetRequestResponse> {

    return await request<PasswordResetRequestResponse>(
        "/api/auth/password-reset-requests",
        {
            method: "POST",
            body: JSON.stringify({
                username,
            }),
        },
    );
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
