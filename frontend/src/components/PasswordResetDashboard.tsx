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
    AdminPasswordResetRequest,
} from "../api/admin";

import {
    approvePasswordReset,
    listPasswordResetRequests,
    rejectPasswordReset,
} from "../api/admin";


export function PasswordResetDashboard() {

    const [requests, setRequests] = useState<
        AdminPasswordResetRequest[]
    >([]);

    const [filter, setFilter] = useState(
        "pending"
    );

    const [loading, setLoading] = useState(
        false
    );

    const [busyRequestId, setBusyRequestId] = useState<
        string | null
    >(null);

    const [error, setError] = useState<string | null>(
        null
    );

    const [notice, setNotice] = useState<string | null>(
        null
    );

    const [temporaryPassword, setTemporaryPassword] = useState<
        string | null
    >(null);

    const [temporaryPasswordUsername, setTemporaryPasswordUsername] = useState<
        string | null
    >(null);

    const [total, setTotal] = useState(0);

    const [offset, setOffset] = useState(0);

    const pageSize = 50;


    const loadRequests = useCallback(
        async () => {

            setLoading(true);
            setError(null);

            try {

                const result = await listPasswordResetRequests(
                    filter === "all" ? null : filter,
                    pageSize,
                    offset,
                );

                setRequests(
                    result.items
                );

                setTotal(
                    result.total
                );

            } catch (error) {

                setError(
                    error instanceof Error
                        ? error.message
                        : "Unable to load password reset requests."
                );

            } finally {

                setLoading(false);
            }
        },
        [filter, offset],
    );


    useEffect(() => {

        void loadRequests();

    }, [loadRequests]);


    async function reviewRequest(
        resetRequest: AdminPasswordResetRequest,
        action: "approve" | "reject",
    ) {

        if (busyRequestId !== null) {
            return;
        }

        const confirmed = window.confirm(
            action === "approve"
                ? (
                    `Approve password reset for ${resetRequest.username}? ` +
                    "Confirm that you have independently verified " +
                    "the account owner's identity."
                )
                : (
                    `Reject password reset for ${resetRequest.username}?`
                )
        );

        if (!confirmed) {
            return;
        }

        setBusyRequestId(
            resetRequest.id
        );

        setError(null);
        setNotice(null);

        try {

            if (action === "approve") {

                const result = await approvePasswordReset(
                    resetRequest.id
                );

                setTemporaryPasswordUsername(
                    resetRequest.username
                );

                setTemporaryPassword(
                    result.temporary_password
                );

                setNotice(
                    result.message
                );

            } else {

                const result = await rejectPasswordReset(
                    resetRequest.id
                );

                setNotice(
                    result.message
                );
            }

            await loadRequests();

        } catch (error) {

            setError(
                error instanceof Error
                    ? error.message
                    : "Unable to process password reset request."
            );

        } finally {

            setBusyRequestId(null);
        }
    }


    function clearTemporaryPassword() {

        setTemporaryPassword(null);
        setTemporaryPasswordUsername(null);
    }


    return (
        <section className="panel">

            <div className="section-header">

                <div>

                    <h2>Password reset requests</h2>

                    <p>
                        Review requests and issue temporary
                        passwords to verified account owners.
                    </p>

                </div>

                <button
                    type="button"
                    className="button secondary"
                    onClick={() => {
                        void loadRequests();
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

            {temporaryPassword !== null && (

                <div
                    className="panel"
                    role="region"
                    aria-label="Temporary password"
                >

                    <h3>Temporary password issued</h3>

                    <p>
                        Account:{" "}
                        <strong>
                            {temporaryPasswordUsername}
                        </strong>
                    </p>

                    <p>
                        This password is displayed only
                        in this session. Provide it to
                        the verified account owner using
                        a trusted communication channel.
                    </p>

                    <label htmlFor="temporary-password">
                        Temporary password
                    </label>

                    <input
                        id="temporary-password"
                        type="text"
                        value={temporaryPassword}
                        readOnly
                        autoComplete="off"
                    />

                    <div className="button-group">

                        <button
                            type="button"
                            className="button secondary"
                            onClick={() => {
                                void navigator.clipboard.writeText(
                                    temporaryPassword
                                );
                            }}
                        >
                            Copy password
                        </button>

                        <button
                            type="button"
                            className="button primary"
                            onClick={clearTemporaryPassword}
                        >
                            Done
                        </button>

                    </div>

                </div>

            )}

            <label htmlFor="password-reset-filter">
                Request status
            </label>

            <select
                id="password-reset-filter"
                value={filter}
                onChange={(event) => {
                    setOffset(0);
                    setFilter(event.target.value);
                }}
            >
                <option value="pending">
                    Pending
                </option>

                <option value="completed">
                    Completed
                </option>

                <option value="rejected">
                    Rejected
                </option>

                <option value="all">
                    All requests
                </option>
            </select>

            {loading ? (

                <p>Loading password reset requests...</p>

            ) : (

                <div className="table-wrapper">

                    <table>

                        <thead>
                            <tr>
                                <th>Username</th>
                                <th>Requested</th>
                                <th>Status</th>
                                <th>Actions</th>
                            </tr>
                        </thead>

                        <tbody>

                            {requests.map((resetRequest) => (

                                <tr key={resetRequest.id}>

                                    <td>
                                        {resetRequest.username}
                                    </td>

                                    <td>
                                        {new Date(
                                            resetRequest.requested_at
                                        ).toLocaleString()}
                                    </td>

                                    <td>
                                        {resetRequest.status}
                                    </td>

                                    <td>

                                        {resetRequest.status === "pending" && (

                                            <div className="button-group">

                                                <button
                                                    type="button"
                                                    className="button primary small"
                                                    disabled={
                                                        busyRequestId !== null ||
                                                        temporaryPassword !== null
                                                    }
                                                    onClick={() => {
                                                        void reviewRequest(
                                                            resetRequest,
                                                            "approve"
                                                        );
                                                    }}
                                                >
                                                    Approve
                                                </button>

                                                <button
                                                    type="button"
                                                    className="button danger small"
                                                    disabled={
                                                        busyRequestId !== null ||
                                                        temporaryPassword !== null
                                                    }
                                                    onClick={() => {
                                                        void reviewRequest(
                                                            resetRequest,
                                                            "reject"
                                                        );
                                                    }}
                                                >
                                                    Reject
                                                </button>

                                            </div>

                                        )}

                                    </td>

                                </tr>

                            ))}

                            {requests.length === 0 && (

                                <tr>
                                    <td
                                        colSpan={4}
                                        className="empty"
                                    >
                                        No password reset requests found.
                                    </td>
                                </tr>

                            )}

                        </tbody>

                    </table>

                </div>

            )}

            <div className="pagination">

                <span>
                    {total} requests
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
                                    offset - pageSize
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
    );
}
