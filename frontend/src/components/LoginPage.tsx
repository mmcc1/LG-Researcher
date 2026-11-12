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

import {
    RegisterPage,
} from "./RegisterPage";

import {
    ForgotPasswordPage,
} from "./ForgotPasswordPage";


export function LoginPage() {

    const { login } = useAuth();

    const [view, setView] = useState<
        "login" | "register" | "forgot-password"
    >("login");

    const [username, setUsername] = useState("");

    const [password, setPassword] = useState("");

    const [submitting, setSubmitting] = useState(false);

    const [error, setError] = useState<string | null>(
        null,
    );


    async function handleSubmit(
        event: FormEvent<HTMLFormElement>,
    ) {

        event.preventDefault();

        if (submitting) {
            return;
        }

        setSubmitting(true);
        setError(null);

        try {

            await login(
                username,
                password,
            );

        } catch (error) {

            setError(
                error instanceof Error
                    ? error.message
                    : "Login failed.",
            );

        } finally {

            setSubmitting(false);
        }
    }


    function openRegistration() {

        setError(null);
        setPassword("");
        setView("register");
    }


    function openForgotPassword() {

        setError(null);
        setPassword("");
        setView("forgot-password");
    }


    function returnToLogin() {

        setError(null);
        setPassword("");
        setView("login");
    }


    if (view === "register") {

        return (
            <RegisterPage
                onBackToLogin={returnToLogin}
            />
        );
    }

    if (view === "forgot-password") {

        return (
            <ForgotPasswordPage
                onBackToLogin={returnToLogin}
            />
        );
    }


    return (
        <div className="auth-page">

            <section className="auth-panel">

                <h1>LG Researcher</h1>

                <p className="muted">
                    Sign in to manage your research.
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

                    <label htmlFor="login-username">
                        Username
                    </label>

                    <input
                        id="login-username"
                        type="text"
                        autoComplete="username"
                        value={username}
                        onChange={(event) => {
                            setUsername(
                                event.target.value,
                            );
                        }}
                        disabled={submitting}
                        required
                    />

                    <label htmlFor="login-password">
                        Password
                    </label>

                    <input
                        id="login-password"
                        type="password"
                        autoComplete="current-password"
                        value={password}
                        onChange={(event) => {
                            setPassword(
                                event.target.value,
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
                            ? "Signing in..."
                            : "Sign in"}
                    </button>

                </form>

                <div className="button-group">

                    <button
                        type="button"
                        className="button secondary"
                        onClick={openRegistration}
                        disabled={submitting}
                    >
                        Register new account
                    </button>

                    <button
                        type="button"
                        className="button secondary"
                        onClick={openForgotPassword}
                        disabled={submitting}
                    >
                        Forgot password?
                    </button>

                </div>

            </section>

        </div>
    );
}
