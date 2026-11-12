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

export class ApiError extends Error {

    readonly status: number;

    constructor(
        status: number,
        message: string,
    ) {

        super(message);

        this.name = "ApiError";
        this.status = status;
    }
}


let csrfToken: string | null = null;


export function setCsrfToken(
    token: string | null,
): void {

    csrfToken = token;
}


export function clearCsrfToken(): void {

    csrfToken = null;
}


export async function request<T>(
    path: string,
    options: RequestInit = {},
): Promise<T> {

    const headers = new Headers(
        options.headers,
    );

    if (options.body !== undefined) {

        headers.set(
            "Content-Type",
            "application/json",
        );
    }

    const method = (
        options.method ?? "GET"
    ).toUpperCase();

    const requiresCsrf = [
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
    ].includes(method);

    if (
        requiresCsrf &&
        csrfToken !== null
    ) {

        headers.set(
            "X-CSRF-Token",
            csrfToken,
        );
    }

    const response = await fetch(
        path,
        {
            ...options,
            headers,
            credentials: "same-origin",
        },
    );

    if (!response.ok) {

        let message = (
            `Request failed (${response.status}).`
        );

        try {

            const body: unknown = (
                await response.json()
            );

            if (
                typeof body === "object" &&
                body !== null &&
                "detail" in body
            ) {

                const detail = body.detail;

                if (
                    typeof detail === "string"
                ) {

                    message = detail;
                }
            }

        } catch {

            // Retain the HTTP status message.
        }

        throw new ApiError(
            response.status,
            message,
        );
    }

    if (response.status === 204) {

        return undefined as T;
    }

    return await response.json() as T;
}
