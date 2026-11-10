
import {
    useState,
} from "react";

import type {
    FormEvent,
} from "react";

import {
    register,
} from "../api/auth";


interface RegisterPageProps {

    onBackToLogin: () => void;
}


export function RegisterPage({
    onBackToLogin,
}: RegisterPageProps) {

    const [username, setUsername] = useState("");

    const [password, setPassword] = useState("");

    const [confirmPassword, setConfirmPassword] = useState("");

    const [submitting, setSubmitting] = useState(false);

    const [error, setError] = useState<string | null>(
        null,
    );

    const [success, setSuccess] = useState<string | null>(
        null,
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
                "Enter a username.",
            );

            return;
        }

        if (password.length < 12) {

            setError(
                "Password must contain at least 12 characters.",
            );

            return;
        }

        if (password !== confirmPassword) {

            setError(
                "Passwords do not match.",
            );

            return;
        }

        setSubmitting(true);

        try {

            const result = await register({
                username: username.trim(),
                password: password,
                confirm_password: confirmPassword,
            });

            setSuccess(
                result.message,
            );

            setPassword("");
            setConfirmPassword("");

        } catch (error) {

            setError(
                error instanceof Error
                    ? error.message
                    : "Registration failed.",
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
                    Create a research account.
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

                        <label htmlFor="register-username">
                            Username
                        </label>

                        <input
                            id="register-username"
                            type="text"
                            autoComplete="username"
                            maxLength={100}
                            value={username}
                            onChange={(event) => {
                                setUsername(
                                    event.target.value,
                                );
                            }}
                            disabled={submitting}
                            required
                        />

                        <label htmlFor="register-password">
                            Password
                        </label>

                        <input
                            id="register-password"
                            type="password"
                            autoComplete="new-password"
                            minLength={12}
                            maxLength={1024}
                            value={password}
                            onChange={(event) => {
                                setPassword(
                                    event.target.value,
                                );
                            }}
                            disabled={submitting}
                            required
                        />

                        <label htmlFor="register-confirm-password">
                            Confirm password
                        </label>

                        <input
                            id="register-confirm-password"
                            type="password"
                            autoComplete="new-password"
                            minLength={12}
                            maxLength={1024}
                            value={confirmPassword}
                            onChange={(event) => {
                                setConfirmPassword(
                                    event.target.value,
                                );
                            }}
                            disabled={submitting}
                            required
                        />

                        <p className="muted">
                            Passwords must contain at least
                            12 characters.
                        </p>

                        <button
                            type="submit"
                            className="button primary"
                            disabled={submitting}
                        >
                            {submitting
                                ? "Registering..."
                                : "Create account"}
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
