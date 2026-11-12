//     LGResearcher - A Langgraph-based LLM agnostic research engine
//     Copyright (C) 2026  Mark McCarron

//     This program is free software: you can redistribute it and/or modify
//     it under the terms of the GNU General Public License as published by
//     the Free Software Foundation, either version 3 of the License, or
//     (at your option) any later version.

//     This program is distributed in the hope that it will be useful,
//     but WITHOUT ANY WARRANTY; without even the implied warranty of
//     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
//     GNU General Public License for more details.

//    You should have received a copy of the GNU General Public License
//     along with this program.  If not, see <https://www.gnu.org/licenses/>

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
