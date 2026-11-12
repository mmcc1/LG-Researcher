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
    useState,
} from "react";

import type {
    FormEvent,
} from "react";

import {
    requestPasswordReset,
} from "../api/auth";


interface ForgotPasswordPageProps {

    onBackToLogin: () => void;
}


export function ForgotPasswordPage({
    onBackToLogin,
}: ForgotPasswordPageProps) {

    const [username, setUsername] = useState("");

    const [submitting, setSubmitting] = useState(false);

    const [error, setError] = useState<string | null>(
        null
    );

    const [success, setSuccess] = useState<string | null>(
        null
    );


    async function handleSubmit(
        event: FormEvent<HTMLFormElement>,
    ) {

        event.preventDefault();

        if (submitting) {
            return;
        }

        setError(null);
        setSuccess(null);

        if (!username.trim()) {

            setError(
                "Enter your username."
            );

            return;
        }

        setSubmitting(true);

        try {

            const result = await requestPasswordReset(
                username.trim()
            );

            setSuccess(
                result.message
            );

        } catch (error) {

            setError(
                error instanceof Error
                    ? error.message
                    : "Unable to submit password reset request."
            );

        } finally {

            setSubmitting(false);
        }
    }


    return (
        <div className="auth-page">

            <section className="auth-panel">

                <h1>LG Researcher</h1>

                <p className="muted">
                    Request a password reset.
                </p>

                <p>
                    Enter your username. If your account
                    is eligible, an administrator can
                    review your password reset request.
                </p>

                {error && (

                    <div
                        className="message error"
                        role="alert"
                    >
                        {error}
                    </div>

                )}

                {success && (

                    <div
                        className="message success"
                        role="status"
                    >
                        {success}
                    </div>

                )}

                {!success && (

                    <form onSubmit={handleSubmit}>

                        <label htmlFor="reset-username">
                            Username
                        </label>

                        <input
                            id="reset-username"
                            type="text"
                            autoComplete="username"
                            maxLength={100}
                            value={username}
                            onChange={(event) => {
                                setUsername(
                                    event.target.value
                                );
                            }}
                            disabled={submitting}
                            required
                        />

                        <button
                            type="submit"
                            className="button primary"
                            disabled={submitting}
                        >
                            {submitting
                                ? "Submitting..."
                                : "Request password reset"}
                        </button>

                    </form>

                )}

                <div className="button-group">

                    <button
                        type="button"
                        className="button secondary"
                        onClick={onBackToLogin}
                        disabled={submitting}
                    >
                        Back to sign in
                    </button>

                </div>

            </section>

        </div>
    );
}
