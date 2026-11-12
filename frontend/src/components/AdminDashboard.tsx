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
    useCallback,
    useEffect,
    useState,
} from "react";

import type {
    AdminUser,
} from "../api/admin";

import {
    approveUser,
    disableUser,
    enableUser,
    listAdminUsers,
    rejectUser,
} from "../api/admin";

import {
    ResearchQueueDashboard,
} from "./ResearchQueueDashboard";

import {
    RecoveryWorkerDashboard,
} from "./RecoveryWorkerDashboard";

import {
    PasswordResetDashboard,
} from "./PasswordResetDashboard";


export function AdminDashboard() {

    const [adminView, setAdminView] = useState<
        "users" | "password-resets" | "research" | "recovery"
    >("users");

    const [users, setUsers] = useState<
        AdminUser[]
    >([]);

    const [filter, setFilter] = useState(
        "pending"
    );

    const [loading, setLoading] = useState(
        false
    );

    const [busyUserId, setBusyUserId] = useState<
        string | null
    >(null);

    const [error, setError] = useState<
        string | null
    >(null);

    const [notice, setNotice] = useState<
        string | null
    >(null);

    const [total, setTotal] = useState(0);

    const [offset, setOffset] = useState(0);

    const pageSize = 50;


    const loadUsers = useCallback(
        async () => {

            setLoading(true);
            setError(null);

            try {

                const result = await listAdminUsers(
                    filter === "all" ? null : filter,
                    pageSize,
                    offset,
                );

                setUsers(result.items);
                setTotal(result.total);

            } catch (error) {

                setError(
                    error instanceof Error
                        ? error.message
                        : "Unable to load users."
                );

            } finally {

                setLoading(false);
            }
        },
        [filter, offset],
    );


    useEffect(() => {

        void loadUsers();

    }, [loadUsers]);


    async function reviewUser(
        userId: string,
        action: "approve" | "reject",
    ) {

        const confirmed = window.confirm(
            action === "approve"
                ? "Approve this user?"
                : "Reject this registration?"
        );

        if (!confirmed) {
            return;
        }

        setBusyUserId(userId);
        setError(null);
        setNotice(null);

        try {

            const result = (
                action === "approve"
                    ? await approveUser(userId)
                    : await rejectUser(userId)
            );

            setNotice(result.message);

            await loadUsers();

        } catch (error) {

            setError(
                error instanceof Error
                    ? error.message
                    : "Unable to review user."
            );

        } finally {

            setBusyUserId(null);
        }
    }


    async function changeUserState(
        userId: string,
        action: "enable" | "disable",
    ) {

        const confirmed = window.confirm(
            action === "enable"
                ? "Enable this user account?"
                : (
                    "Disable this user account? " +
                    "All existing sessions will be revoked."
                )
        );

        if (!confirmed) {
            return;
        }

        setBusyUserId(userId);
        setError(null);
        setNotice(null);

        try {

            const result = (
                action === "enable"
                    ? await enableUser(userId)
                    : await disableUser(userId)
            );

            setNotice(result.message);

            await loadUsers();

        } catch (error) {

            setError(
                error instanceof Error
                    ? error.message
                    : "Unable to change user account state."
            );

        } finally {

            setBusyUserId(null);
        }
    }


    return (
        <div className="app-shell">

            <main className="main-content">

                <div className="button-group">

                    <button
                        type="button"
                        className="button secondary"
                        aria-pressed={adminView === "users"}
                        onClick={() => {
                            setAdminView("users");
                        }}
                    >
                        User Administration
                    </button>

                    <button
                        type="button"
                        className="button secondary"
                        aria-pressed={adminView === "password-resets"}
                        onClick={() => {
                            setAdminView("password-resets");
                        }}
                    >
                        Password Resets
                    </button>

                    <button
                        type="button"
                        className="button secondary"
                        aria-pressed={adminView === "research"}
                        onClick={() => {
                            setAdminView("research");
                        }}
                    >
                        Research Queue
                    </button>

                    <button
                        type="button"
                        className="button secondary"
                        aria-pressed={adminView === "recovery"}
                        onClick={() => {
                            setAdminView("recovery");
                        }}
                    >
                        Recovery Worker
                    </button>

                </div>

                {adminView === "research" ? (

                    <ResearchQueueDashboard />

                ) : adminView === "recovery" ? (

                    <RecoveryWorkerDashboard />

                ) : adminView === "password-resets" ? (

                    <PasswordResetDashboard />

                ) : (

                    <section className="panel">

                        <div className="section-header">

                            <div>
                                <h2>User administration</h2>

                                <p>
                                    Review registrations and
                                    inspect user accounts.
                                </p>
                            </div>

                            <button
                                type="button"
                                className="button secondary"
                                onClick={() => {
                                    void loadUsers();
                                }}
                                disabled={loading}
                            >
                                Refresh
                            </button>

                        </div>

                        {error && (
                            <div
                                className="message error"
                                role="alert"
                            >
                                {error}
                            </div>
                        )}

                        {notice && (
                            <div
                                className="message success"
                                role="status"
                            >
                                {notice}
                            </div>
                        )}

                        <label htmlFor="user-filter">
                            Account status
                        </label>

                        <select
                            id="user-filter"
                            value={filter}
                            onChange={(event) => {
                                setOffset(0);
                                setFilter(event.target.value);
                            }}
                        >
                            <option value="pending">
                                Pending approval
                            </option>
                            <option value="approved">
                                Approved
                            </option>
                            <option value="rejected">
                                Rejected
                            </option>
                            <option value="all">
                                All users
                            </option>
                        </select>

                        {loading ? (
                            <p>Loading users...</p>
                        ) : (
                            <div className="table-wrapper">

                                <table>
                                    <thead>
                                        <tr>
                                            <th>Username</th>
                                            <th>Role</th>
                                            <th>Status</th>
                                            <th>Active</th>
                                            <th>Created</th>
                                            <th>Actions</th>
                                        </tr>
                                    </thead>

                                    <tbody>

                                        {users.map((user) => (
                                            <tr key={user.id}>

                                                <td>{user.username}</td>

                                                <td>{user.role}</td>

                                                <td>
                                                    {user.approval_status}
                                                </td>

                                                <td>
                                                    {user.is_active
                                                        ? "Yes"
                                                        : "No"}
                                                </td>

                                                <td>
                                                    {new Date(
                                                        user.created_at
                                                    ).toLocaleString()}
                                                </td>

                                                <td>

                                                    {user.approval_status
                                                        === "pending" &&
                                                        user.role === "user" && (

                                                        <div className="button-group">

                                                            <button
                                                                type="button"
                                                                className="button primary small"
                                                                disabled={
                                                                    busyUserId !== null
                                                                }
                                                                onClick={() => {
                                                                    void reviewUser(
                                                                        user.id,
                                                                        "approve",
                                                                    );
                                                                }}
                                                            >
                                                                Approve
                                                            </button>

                                                            <button
                                                                type="button"
                                                                className="button danger small"
                                                                disabled={
                                                                    busyUserId !== null
                                                                }
                                                                onClick={() => {
                                                                    void reviewUser(
                                                                        user.id,
                                                                        "reject",
                                                                    );
                                                                }}
                                                            >
                                                                Reject
                                                            </button>

                                                        </div>

                                                    )}

                                                    {user.approval_status
                                                        === "approved" &&
                                                        user.role === "user" && (

                                                        <div className="button-group">

                                                            {user.is_active ? (

                                                                <button
                                                                    type="button"
                                                                    className="button danger small"
                                                                    disabled={
                                                                        busyUserId !== null
                                                                    }
                                                                    onClick={() => {
                                                                        void changeUserState(
                                                                            user.id,
                                                                            "disable",
                                                                        );
                                                                    }}
                                                                >
                                                                    Disable
                                                                </button>

                                                            ) : (

                                                                <button
                                                                    type="button"
                                                                    className="button primary small"
                                                                    disabled={
                                                                        busyUserId !== null
                                                                    }
                                                                    onClick={() => {
                                                                        void changeUserState(
                                                                            user.id,
                                                                            "enable",
                                                                        );
                                                                    }}
                                                                >
                                                                    Enable
                                                                </button>

                                                            )}

                                                        </div>

                                                    )}

                                                </td>

                                            </tr>
                                        ))}

                                        {users.length === 0 && (
                                            <tr>
                                                <td
                                                    colSpan={6}
                                                    className="empty"
                                                >
                                                    No users found.
                                                </td>
                                            </tr>
                                        )}

                                    </tbody>
                                </table>

                            </div>
                        )}

                        <div className="pagination">

                            <span>
                                {total} users
                            </span>

                            <div className="button-group">

                                <button
                                    type="button"
                                    className="button secondary"
                                    disabled={
                                        loading || offset === 0
                                    }
                                    onClick={() => {
                                        setOffset(
                                            Math.max(
                                                0,
                                                offset - pageSize,
                                            )
                                        );
                                    }}
                                >
                                    Previous
                                </button>

                                <button
                                    type="button"
                                    className="button secondary"
                                    disabled={
                                        loading ||
                                        offset + pageSize >= total
                                    }
                                    onClick={() => {
                                        setOffset(
                                            offset + pageSize
                                        );
                                    }}
                                >
                                    Next
                                </button>

                            </div>

                        </div>

                    </section>

                )}

            </main>

        </div>
    );
}
