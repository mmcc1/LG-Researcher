
import App from "./App";

import {
    ChangePasswordPage,
} from "./components/ChangePasswordPage";

import {
    LoginPage,
} from "./components/LoginPage";

import {
    useAuth,
} from "./context/AuthContext";

import {
    useState,
} from "react";

import {
    AdminDashboard,
} from "./components/AdminDashboard";


export function AuthenticatedApp() {

    const {
        user,
        loading,
        logout,
    } = useAuth();

    const [view, setView] = useState<
        "research" | "admin"
    >("research");

    if (loading) {

        return (
            <div className="auth-page">
                <p>Checking session...</p>
            </div>
        );
    }

    if (user === null) {

        return <LoginPage />;
    }

    if (user.must_change_password) {

        return <ChangePasswordPage />;
    }

    
    return (
        <>
            <div className="auth-toolbar">

                <div className="button-group">

                    <button
                        type="button"
                        className="button secondary small"
                        onClick={() => {
                            setView("research");
                        }}
                    >
                        Research
                    </button>

                    {user.role === "admin" && (

                        <button
                            type="button"
                            className="button secondary small"
                            onClick={() => {
                                setView("admin");
                            }}
                        >
                            Administration
                        </button>

                    )}

                </div>

                <span>
                    Signed in as{" "}
                    <strong>{user.username}</strong>
                    {" "}
                    ({user.role})
                </span>

                <button
                    type="button"
                    className="button secondary small"
                    onClick={() => {
                        void logout().catch(
                            (error: unknown) => {
                                console.error(
                                    "Logout failed.",
                                    error,
                                );
                            },
                        );
                    }}
                >
                    Sign out
                </button>

            </div>

            {view === "admin" && user.role === "admin"
                ? <AdminDashboard />
                : <App />}

        </>
    );

}
