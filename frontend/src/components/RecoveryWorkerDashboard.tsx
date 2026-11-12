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
    useRef,
    useState,
} from "react";

import type {
    AdminRecoveryHealthResponse,
    AdminRecoveryHealthSnapshot,
} from "../api/admin";

import {
    getAdminRecoveryHealth,
} from "../api/admin";


function formatDate(
    value: string | null,
): string {

    if (value === null) {
        return "—";
    }

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
        return value;
    }

    return date.toLocaleString();
}


function formatDuration(
    value: number | null,
): string {

    if (value === null) {
        return "—";
    }

    return `${value.toFixed(3)} seconds`;
}


export function RecoveryWorkerDashboard() {

    const [response, setResponse] = useState<
        AdminRecoveryHealthResponse | null
    >(null);

    const [loading, setLoading] = useState(false);

    const [error, setError] = useState<
        string | null
    >(null);

    const [refreshVersion, setRefreshVersion] = useState(0);

    const [autoRefresh, setAutoRefresh] = useState(true);

    const [refreshInterval, setRefreshInterval] = useState(10);

    const loadingRef = useRef(false);


    const loadHealth = useCallback(
        async (signal: AbortSignal) => {

            loadingRef.current = true;

            setLoading(true);
            setError(null);

            try {

                const result = await getAdminRecoveryHealth(
                    signal
                );

                if (signal.aborted) {
                    return;
                }

                setResponse(result);

            } catch (caughtError) {

                if (signal.aborted) {
                    return;
                }

                setError(
                    caughtError instanceof Error
                        ? caughtError.message
                        : "Unable to load recovery health."
                );

            } finally {

                if (!signal.aborted) {

                    loadingRef.current = false;

                    setLoading(false);
                }
            }
        },
        [],
    );


    useEffect(() => {

        const controller = new AbortController();

        void loadHealth(controller.signal);

        return () => {

            controller.abort();

            loadingRef.current = false;
        };

    }, [loadHealth, refreshVersion]);


    useEffect(() => {

        if (!autoRefresh) {
            return;
        }

        const intervalId = window.setInterval(
            () => {

                if (document.visibilityState !== "visible") {
                    return;
                }

                if (loadingRef.current) {
                    return;
                }

                setRefreshVersion(
                    (current) => current + 1
                );
            },
            refreshInterval * 1000,
        );

        return () => {
            window.clearInterval(intervalId);
        };

    }, [autoRefresh, refreshInterval]);


    function refresh() {

        setRefreshVersion(
            (current) => current + 1
        );
    }


    const health: AdminRecoveryHealthSnapshot | null = (
        error === null && response?.available
            ? response.health
            : null
    );


    return (
        <section className="panel">

            <div className="section-header">

                <div>
                    <h2>Recovery worker</h2>

                    <p>
                        Monitor the existing research
                        recovery service.
                    </p>
                </div>

                <button
                    type="button"
                    className="button secondary"
                    disabled={loading}
                    onClick={refresh}
                >
                    Refresh
                </button>

            </div>

            <div className="queue-controls">

                <label htmlFor="recovery-auto-refresh">

                    <input
                        id="recovery-auto-refresh"
                        type="checkbox"
                        checked={autoRefresh}
                        onChange={(event) => {
                            setAutoRefresh(
                                event.target.checked
                            );
                        }}
                    />

                    Automatic refresh

                </label>

                <label htmlFor="recovery-refresh-interval">
                    Refresh every
                </label>

                <select
                    id="recovery-refresh-interval"
                    value={refreshInterval}
                    disabled={!autoRefresh}
                    onChange={(event) => {
                        setRefreshInterval(
                            Number(event.target.value)
                        );
                    }}
                >
                    <option value={5}>5 seconds</option>
                    <option value={10}>10 seconds</option>
                    <option value={30}>30 seconds</option>
                    <option value={60}>60 seconds</option>
                </select>

            </div>

            {loading && (
                <p role="status">
                    Loading recovery health...
                </p>
            )}

            {error !== null && (
                <div
                    className="message error"
                    role="alert"
                >
                    {error}
                </div>
            )}

            {!loading && error === null &&
                response?.available === false && (

                <p>
                    Recovery health monitoring is unavailable.
                    The API may not be configured with the
                    health-file path, or the snapshot may not
                    have been created yet.
                </p>

            )}

            {health !== null && (

                <>
                    <div className="queue-summary">

                        <div className="queue-summary-item">
                            <strong>{health.state}</strong>
                            <span>Reported state</span>
                        </div>

                        <div className="queue-summary-item">
                            <strong>{health.pid}</strong>
                            <span>Process ID</span>
                        </div>

                        <div className="queue-summary-item">
                            <strong>{health.cycles}</strong>
                            <span>Completed cycles</span>
                        </div>

                        <div className="queue-summary-item">
                            <strong>{health.resumed}</strong>
                            <span>Resumed</span>
                        </div>

                        <div className="queue-summary-item">
                            <strong>{health.paused}</strong>
                            <span>Paused</span>
                        </div>

                        <div className="queue-summary-item">
                            <strong>{health.skipped}</strong>
                            <span>Skipped</span>
                        </div>

                        <div className="queue-summary-item">
                            <strong>{health.failed_sessions}</strong>
                            <span>Failed sessions</span>
                        </div>

                        <div className="queue-summary-item">
                            <strong>{health.cycle_errors}</strong>
                            <span>Cycle errors</span>
                        </div>

                    </div>

                    <div className="table-wrapper">

                        <table>
                            <tbody>

                                <tr>
                                    <th>Started</th>
                                    <td>
                                        {formatDate(health.started_at)}
                                    </td>
                                </tr>

                                <tr>
                                    <th>Snapshot updated</th>
                                    <td>
                                        {formatDate(health.updated_at)}
                                    </td>
                                </tr>

                                <tr>
                                    <th>Last cycle</th>
                                    <td>
                                        {formatDate(health.last_cycle_at)}
                                    </td>
                                </tr>

                                <tr>
                                    <th>Last successful cycle</th>
                                    <td>
                                        {formatDate(health.last_success_at)}
                                    </td>
                                </tr>

                                <tr>
                                    <th>Last cycle duration</th>
                                    <td>
                                        {formatDuration(
                                            health.last_cycle_duration_seconds
                                        )}
                                    </td>
                                </tr>

                            </tbody>
                        </table>

                    </div>

                    {health.last_error !== null && (

                        <div
                            className="message error"
                            role="alert"
                        >
                            <strong>Last recorded cycle error:</strong>
                            {" "}
                            {health.last_error}
                        </div>

                    )}

                    <p>
                        The reported state comes from the
                        recovery worker's JSON snapshot.
                        It does not independently confirm
                        that the Windows service is running.
                    </p>

                </>

            )}

        </section>
    );
}
