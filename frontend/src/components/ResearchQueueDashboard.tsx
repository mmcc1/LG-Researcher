
import {
    useCallback,
    useEffect,
    useRef,
    useState,
} from "react";

import type {
    AdminResearchJob,
    AdminResearchJobSummary,
} from "../api/admin";

import {
    getAdminResearchJobSummary,
    listAdminResearchJobs,
} from "../api/admin";


const PAGE_SIZE = 50;


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


export function ResearchQueueDashboard() {

    const [jobs, setJobs] = useState<
        AdminResearchJob[]
    >([]);

    const [summary, setSummary] = useState<
        AdminResearchJobSummary | null
    >(null);

    const [filter, setFilter] = useState(
        "all"
    );

    const [offset, setOffset] = useState(0);

    const [total, setTotal] = useState(0);

    const [loading, setLoading] = useState(
        false
    );

    const [error, setError] = useState<
        string | null
    >(null);

    const [refreshVersion, setRefreshVersion] = useState(0);

    const [autoRefresh, setAutoRefresh] = useState(
        true
    );

    const [refreshInterval, setRefreshInterval] = useState(
        10
    );

    const loadingRef = useRef(false);


    const loadJobs = useCallback(
        async (signal: AbortSignal) => {

            loadingRef.current = true;

            setLoading(true);
            setError(null);

            try {

                const jobStatus = (
                    filter === "all"
                        ? null
                        : filter
                );

                const [jobResult, summaryResult] =
                    await Promise.all([
                        listAdminResearchJobs(
                            jobStatus,
                            PAGE_SIZE,
                            offset,
                            signal,
                        ),
                        getAdminResearchJobSummary(
                            signal,
                        ),
                    ]);

                if (signal.aborted) {
                    return;
                }

                setJobs(jobResult.items);
                setTotal(jobResult.total);
                setSummary(summaryResult);

            } catch (caughtError) {

                if (signal.aborted) {
                    return;
                }

                setError(
                    caughtError instanceof Error
                        ? caughtError.message
                        : "Unable to load research jobs."
                );

            } finally {

                if (!signal.aborted) {

                    loadingRef.current = false;

                    setLoading(false);
                }
            }
        },
        [filter, offset],
    );


    useEffect(() => {

        const controller = new AbortController();

        void loadJobs(controller.signal);

        return () => {

            controller.abort();

            loadingRef.current = false;
        };

    }, [loadJobs, refreshVersion]);


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


    const statuses = summary?.statuses ?? [];

    const statusOptions = Array.from(
        new Set([
            "draft",
            "queued",
            "running",
            "completed",
            "failed",
            ...statuses.map(
                (item) => item.status
            ),
        ])
    );

    const counts = new Map(
        statuses.map(
            (item) => [
                item.status,
                item.count,
            ]
        )
    );


    return (
        <section className="panel">

            <div className="section-header">

                <div>
                    <h2>Research queue</h2>

                    <p>
                        Monitor research jobs across
                        all registered users.
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

            {error && (
                <div
                    className="message error"
                    role="alert"
                >
                    {error}
                </div>
            )}

            {summary !== null && (

                <div className="queue-summary">

                    <div className="queue-summary-item">
                        <strong>{summary.total}</strong>
                        <span>Total jobs</span>
                    </div>

                    {statuses.map((item) => (

                        <div
                            key={item.status}
                            className="queue-summary-item"
                        >
                            <strong>{item.count}</strong>
                            <span>{item.status}</span>
                        </div>

                    ))}

                </div>

            )}

            <div className="queue-controls">

                <label htmlFor="research-status-filter">
                    Job status
                </label>

                <select
                    id="research-status-filter"
                    value={filter}
                    onChange={(event) => {

                        setOffset(0);

                        setFilter(
                            event.target.value
                        );
                    }}
                >
                    <option value="all">
                        All statuses
                    </option>

                    {statusOptions.map((status) => (

                        <option
                            key={status}
                            value={status}
                        >
                            {status} ({counts.get(status) ?? 0})
                        </option>

                    ))}
                </select>

                <label htmlFor="queue-auto-refresh">

                    <input
                        id="queue-auto-refresh"
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

                <label htmlFor="queue-refresh-interval">
                    Refresh every
                </label>

                <select
                    id="queue-refresh-interval"
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
                    Loading research jobs...
                </p>
            )}

            <div className="table-wrapper">

                <table>
                    <thead>
                        <tr>
                            <th>Topic</th>
                            <th>User</th>
                            <th>Status</th>
                            <th>Created</th>
                            <th>Started</th>
                            <th>Completed</th>
                            <th>Execution</th>
                        </tr>
                    </thead>

                    <tbody>

                        {jobs.map((job) => (

                            <tr key={job.id}>

                                <td>
                                    <strong>{job.topic}</strong>

                                    {job.last_error && (
                                        <p
                                            className="message error"
                                            role="alert"
                                        >
                                            {job.last_error}
                                        </p>
                                    )}
                                </td>

                                <td>
                                    {job.username}
                                </td>

                                <td>
                                    {job.status}
                                </td>

                                <td>
                                    {formatDate(job.created_at)}
                                </td>

                                <td>
                                    {formatDate(job.started_at)}
                                </td>

                                <td>
                                    {formatDate(job.completed_at)}
                                </td>

                                <td>
                                    {job.execution_owner
                                        ? (
                                            <>
                                                <div>
                                                    Worker: {job.execution_owner}
                                                </div>

                                                <div>
                                                    Lease expires:{" "}
                                                    {formatDate(
                                                        job.lease_expires_at
                                                    )}
                                                </div>
                                            </>
                                        )
                                        : "—"}
                                </td>

                            </tr>

                        ))}

                        {!loading && jobs.length === 0 && (
                            <tr>
                                <td
                                    colSpan={7}
                                    className="empty"
                                >
                                    No research jobs found.
                                </td>
                            </tr>
                        )}

                    </tbody>
                </table>

            </div>

            <div className="pagination">

                <span>
                    {total} matching jobs
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
                                    offset - PAGE_SIZE,
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
                            offset + PAGE_SIZE >= total
                        }
                        onClick={() => {
                            setOffset(
                                offset + PAGE_SIZE
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
