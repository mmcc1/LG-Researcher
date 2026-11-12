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
