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
    useAuth,
} from "../context/AuthContext";


export function ChangePasswordPage() {

    const {
        user,
        changePassword,
        logout,
    } = useAuth();

    const [currentPassword, setCurrentPassword] = (
        useState("")
    );

    const [newPassword, setNewPassword] = (
        useState("")
    );

    const [confirmPassword, setConfirmPassword] = (
        useState("")
    );

    const [submitting, setSubmitting] = (
        useState(false)
    );

    const [error, setError] = useState<string | null>(
        null
    );


    async function handleSubmit(
        event: FormEvent<HTMLFormElement>,
    ) {

        event.preventDefault();

        if (submitting) {
            return;
        }

        if (newPassword !== confirmPassword) {

            setError(
                "New passwords do not match."
            );

            return;
        }

        setSubmitting(true);
        setError(null);

        try {

            await changePassword(
                currentPassword,
                newPassword,
            );

        } catch (error) {

            setError(
                error instanceof Error
                    ? error.message
                    : "Password change failed.",
            );

        } finally {

            setSubmitting(false);
        }
    }


    async function handleLogout() {

        setSubmitting(true);
        setError(null);

        try {

            await logout();

        } catch (error) {

            setError(
                error instanceof Error
                    ? error.message
                    : "Logout failed.",
            );

        } finally {

            setSubmitting(false);
        }
    }


    return (
        <div className="auth-page">

            <section className="auth-panel">

                <h1>Change password</h1>

                <p className="muted">
                    Signed in as {user?.username}.
                    You must change your password
                    before accessing research jobs.
                </p>

                {error && (
                    <div
                        className="message error"
                        role="alert"
                    >
                        {error}
                    </div>
                )}

                <form onSubmit={handleSubmit}>

                    <label htmlFor="current-password">
                        Current password
                    </label>

                    <input
                        id="current-password"
                        type="password"
                        autoComplete="current-password"
                        value={currentPassword}
                        onChange={(event) => {
                            setCurrentPassword(
                                event.target.value
                            );
                        }}
                        required
                    />

                    <label htmlFor="new-password">
                        New password
                    </label>

                    <input
                        id="new-password"
                        type="password"
                        autoComplete="new-password"
                        minLength={12}
                        value={newPassword}
                        onChange={(event) => {
                            setNewPassword(
                                event.target.value
                            );
                        }}
                        required
                    />

                    <label htmlFor="confirm-password">
                        Confirm new password
                    </label>

                    <input
                        id="confirm-password"
                        type="password"
                        autoComplete="new-password"
                        minLength={12}
                        value={confirmPassword}
                        onChange={(event) => {
                            setConfirmPassword(
                                event.target.value
                            );
                        }}
                        required
                    />

                    <div className="button-group">

                        <button
                            type="submit"
                            className="button primary"
                            disabled={submitting}
                        >
                            Change password
                        </button>

                        <button
                            type="button"
                            className="button secondary"
                            disabled={submitting}
                            onClick={() => {
                                void handleLogout();
                            }}
                        >
                            Sign out
                        </button>

                    </div>

                </form>

            </section>

        </div>
    );
}
