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
    FormEvent,
} from "react";

import type {
    ResearchJob,
    ResearchJobSummary,
} from "./api/researchJobs";

import {
    addResearchQuestion,
    createResearchJob,
    getResearchJob,
    listResearchJobs,
    pauseResearchJob,
    removeResearchQuestion,
    resumeResearchJob,
    submitResearchJob,
    updateResearchJob,
} from "./api/researchJobs";

import "./App.css";


const pageSize = 10;

const refreshIntervalMilliseconds = 5000;


function errorMessage(error: unknown): string {

    if (error instanceof Error) {
        return error.message;
    }

    return "An unexpected error occurred.";
}


function formatDate(
    value: string | null,
): string {

    if (!value) {
        return "—";
    }

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
        return value;
    }

    return date.toLocaleString();
}


function App() {

    const [jobs, setJobs] = useState<
        ResearchJobSummary[]
    >([]);

    const [total, setTotal] = useState(0);

    const [offset, setOffset] = useState(0);

    const [selectedJob, setSelectedJob] = useState<
        ResearchJob | null
    >(null);

    const [view, setView] = useState<
        "dashboard" | "new" | "details"
    >("dashboard");

    const [topic, setTopic] = useState("");

    const [scope, setScope] = useState("");

    const [newQuestion, setNewQuestion] = useState("");

    const [loading, setLoading] = useState(false);

    const [saving, setSaving] = useState(false);

    const [error, setError] = useState<string | null>(
        null,
    );

    const [notice, setNotice] = useState<string | null>(
        null,
    );

    const [pausePendingJobId, setPausePendingJobId] = useState<
        string | null
    >(null);

    const refreshInProgressRef = useRef(false);


    const loadJobs = useCallback(
        async () => {

            setLoading(true);
            setError(null);

            try {

                const result = await listResearchJobs(
                    pageSize,
                    offset,
                );

                setJobs(result.items);
                setTotal(result.total);

            } catch (error) {

                setError(
                    errorMessage(error),
                );

            } finally {

                setLoading(false);
            }
        },
        [offset],
    );


    useEffect(
        () => {

            if (view === "dashboard") {
                void loadJobs();
            }

        },
        [view, loadJobs],
    );


    useEffect(() => {

        if (
            view !== "details" ||
            selectedJob === null ||
            saving
        ) {
            return;
        }

        const jobId = selectedJob.id;

        const refreshableStatuses = new Set([
            "queued",
            "claimed",
            "pause_requested",
        ]);

        if (
            !refreshableStatuses.has(
                selectedJob.status
            )
        ) {
            return;
        }

        let cancelled = false;

        const refreshJob = async () => {

            if (
                cancelled ||
                document.visibilityState !== "visible" ||
                refreshInProgressRef.current
            ) {
                return;
            }

            refreshInProgressRef.current = true;

            try {

                const job = await getResearchJob(
                    jobId,
                );

                if (!cancelled) {

                    setSelectedJob(job);

                    if (job.status !== "claimed") {

                        setPausePendingJobId(
                            (current) => (
                                current === jobId
                                    ? null
                                    : current
                            ),
                        );
                    }
                }

            } catch (error) {

                if (!cancelled) {

                    console.error(
                        "Unable to refresh research job.",
                        error,
                    );
                }

            } finally {

                refreshInProgressRef.current = false;
            }
        };

        const intervalId = window.setInterval(
            () => {
                void refreshJob();
            },
            refreshIntervalMilliseconds,
        );

        return () => {

            cancelled = true;

            window.clearInterval(
                intervalId,
            );
        };

    }, [
        view,
        selectedJob?.id,
        selectedJob?.status,
        saving,
    ]);


    async function openJob(
        jobId: string,
    ) {

        setLoading(true);
        setError(null);
        setNotice(null);

        try {

            const job = await getResearchJob(
                jobId,
            );

            setSelectedJob(job);
            setTopic(job.topic);
            setScope(job.scope ?? "");
            setNewQuestion("");
            setPausePendingJobId(null);
            setView("details");

        } catch (error) {

            setError(
                errorMessage(error),
            );

        } finally {

            setLoading(false);
        }
    }


    function openNewJob() {

        setSelectedJob(null);
        setTopic("");
        setScope("");
        setNewQuestion("");
        setPausePendingJobId(null);
        setError(null);
        setNotice(null);
        setView("new");
    }


    function returnToDashboard() {

        setSelectedJob(null);
        setPausePendingJobId(null);
        setError(null);
        setNotice(null);
        setView("dashboard");
    }


    async function refreshSelectedJob(
        jobId: string,
    ) {

        const job = await getResearchJob(
            jobId,
        );

        setSelectedJob(job);

        if (job.status !== "claimed") {

            setPausePendingJobId(
                (current) => (
                    current === jobId
                        ? null
                        : current
                ),
            );
        }

        return job;
    }


    async function createJob(
        event: FormEvent<HTMLFormElement>,
    ) {

        event.preventDefault();

        if (!topic.trim()) {
            setError("Enter a research topic.");
            return;
        }

        setSaving(true);
        setError(null);
        setNotice(null);

        try {

            const job = await createResearchJob({
                topic: topic.trim(),
                scope: scope.trim() || null,
            });

            setSelectedJob(job);
            setTopic(job.topic);
            setScope(job.scope ?? "");
            setView("details");

            setNotice(
                "Research job created.",
            );

        } catch (error) {

            setError(
                errorMessage(error),
            );

        } finally {

            setSaving(false);
        }
    }


    async function saveJob(
        event: FormEvent<HTMLFormElement>,
    ) {

        event.preventDefault();

        if (!selectedJob) {
            return;
        }

        if (!topic.trim()) {
            setError("Enter a research topic.");
            return;
        }

        setSaving(true);
        setError(null);
        setNotice(null);

        try {

            const job = await updateResearchJob(
                selectedJob.id,
                {
                    topic: topic.trim(),
                    scope: scope.trim() || null,
                },
            );

            setSelectedJob(job);
            setTopic(job.topic);
            setScope(job.scope ?? "");

            setNotice(
                "Draft updated successfully.",
            );

        } catch (error) {

            setError(
                errorMessage(error),
            );

        } finally {

            setSaving(false);
        }
    }


    async function addQuestion(
        event: FormEvent<HTMLFormElement>,
    ) {

        event.preventDefault();

        if (!selectedJob || !newQuestion.trim()) {
            return;
        }

        setSaving(true);
        setError(null);
        setNotice(null);

        try {

            await addResearchQuestion(
                selectedJob.id,
                newQuestion.trim(),
            );

            await refreshSelectedJob(
                selectedJob.id,
            );

            setNewQuestion("");

            setNotice(
                "Research question added.",
            );

        } catch (error) {

            setError(
                errorMessage(error),
            );

        } finally {

            setSaving(false);
        }
    }


    async function removeQuestion(
        questionId: number,
    ) {

        if (!selectedJob) {
            return;
        }

        setSaving(true);
        setError(null);
        setNotice(null);

        try {

            await removeResearchQuestion(
                selectedJob.id,
                questionId,
            );

            await refreshSelectedJob(
                selectedJob.id,
            );

            setNotice(
                "Research question removed.",
            );

        } catch (error) {

            setError(
                errorMessage(error),
            );

        } finally {

            setSaving(false);
        }
    }


    async function submitJob() {

        if (!selectedJob || saving) {
            return;
        }

        if (
            !window.confirm(
                "Submit this research job? " +
                "The draft will become read-only.",
            )
        ) {
            return;
        }

        setSaving(true);
        setError(null);
        setNotice(null);

        try {

            await submitResearchJob(
                selectedJob.id,
            );

            const job = await refreshSelectedJob(
                selectedJob.id,
            );

            setTopic(job.topic);
            setScope(job.scope ?? "");

            setNotice(
                "Research job submitted successfully.",
            );

        } catch (error) {

            setError(
                errorMessage(error),
            );

        } finally {

            setSaving(false);
        }
    }


    async function pauseJob() {

        if (!selectedJob || saving) {
            return;
        }

        const jobId = selectedJob.id;

        if (
            !window.confirm(
                "Pause this research job? " +
                "Running research will pause at the next " +
                "available checkpoint.",
            )
        ) {
            return;
        }

        setSaving(true);
        setError(null);
        setNotice(null);

        try {

            const result = await pauseResearchJob(
                jobId,
            );

            if (result.status === "pause_requested") {

                setPausePendingJobId(jobId);

            } else {

                setPausePendingJobId(null);
            }

            const job = await refreshSelectedJob(
                jobId,
            );

            if (job.status === "paused") {

                setPausePendingJobId(null);

                setNotice(
                    "Research job paused.",
                );

            } else if (
                result.status === "pause_requested"
            ) {

                setNotice(
                    "Pause requested. Research will pause " +
                    "at the next available checkpoint.",
                );

            } else {

                setNotice(
                    `Pause request result: ${result.status}`,
                );
            }

        } catch (error) {

            setError(
                errorMessage(error),
            );

        } finally {

            setSaving(false);
        }
    }


    async function resumeJob() {

        if (!selectedJob || saving) {
            return;
        }

        const jobId = selectedJob.id;

        setSaving(true);
        setError(null);
        setNotice(null);

        try {

            await resumeResearchJob(
                jobId,
            );

            setPausePendingJobId(null);

            await refreshSelectedJob(
                jobId,
            );

            setNotice(
                "Research job resumed and returned to the queue.",
            );

        } catch (error) {

            setError(
                errorMessage(error),
            );

        } finally {

            setSaving(false);
        }
    }


    const isDraft = (
        selectedJob?.status === "draft"
    );

    const canPause = (
        selectedJob?.status === "queued" ||
        selectedJob?.status === "claimed"
    );

    const canResume = (
        selectedJob?.status === "paused"
    );

    const pausePending = (
        selectedJob !== null &&
        pausePendingJobId === selectedJob.id &&
        selectedJob.status === "claimed"
    );

    const pageNumber = (
        Math.floor(offset / pageSize) + 1
    );

    const pageCount = Math.max(
        1,
        Math.ceil(total / pageSize),
    );


    return (
        <div className="app-shell">

            <header className="app-header">

                <div>
                    <h1>LG Researcher</h1>

                    <p>
                        Research job management
                    </p>
                </div>

                <button
                    type="button"
                    className="button secondary"
                    onClick={returnToDashboard}
                    disabled={saving}
                >
                    Dashboard
                </button>

            </header>

            <main className="main-content">

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

                {view === "dashboard" && (

                    <section className="panel">

                        <div className="section-header">

                            <div>
                                <h2>Research jobs</h2>

                                <p>
                                    Manage drafts and monitor
                                    submitted research.
                                </p>
                            </div>

                            <button
                                type="button"
                                className="button primary"
                                onClick={openNewJob}
                            >
                                New research job
                            </button>

                        </div>

                        {loading ? (

                            <p>Loading jobs...</p>

                        ) : (

                            <>

                                <div className="table-wrapper">

                                    <table>

                                        <thead>
                                            <tr>
                                                <th>Topic</th>
                                                <th>Status</th>
                                                <th>Created</th>
                                                <th>Session</th>
                                                <th></th>
                                            </tr>
                                        </thead>

                                        <tbody>

                                            {jobs.map((job) => (

                                                <tr key={job.id}>

                                                    <td>
                                                        {job.topic}
                                                    </td>

                                                    <td>
                                                        <span
                                                            className={
                                                                "status " +
                                                                job.status
                                                            }
                                                        >
                                                            {job.status}
                                                        </span>
                                                    </td>

                                                    <td>
                                                        {formatDate(
                                                            job.created_at,
                                                        )}
                                                    </td>

                                                    <td className="session-id">
                                                        {job.research_session_id
                                                            ?? "—"}
                                                    </td>

                                                    <td>
                                                        <button
                                                            type="button"
                                                            className="button small"
                                                            onClick={() => {
                                                                void openJob(
                                                                    job.id,
                                                                );
                                                            }}
                                                        >
                                                            Open
                                                        </button>
                                                    </td>

                                                </tr>

                                            ))}

                                            {jobs.length === 0 && (

                                                <tr>
                                                    <td
                                                        colSpan={5}
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
                                        Page {pageNumber} of {pageCount}
                                        {" · "}
                                        {total} jobs
                                    </span>

                                    <div className="button-group">

                                        <button
                                            type="button"
                                            className="button secondary"
                                            disabled={offset === 0}
                                            onClick={() => {
                                                setOffset(
                                                    Math.max(
                                                        0,
                                                        offset - pageSize,
                                                    ),
                                                );
                                            }}
                                        >
                                            Previous
                                        </button>

                                        <button
                                            type="button"
                                            className="button secondary"
                                            disabled={
                                                offset + pageSize >= total
                                            }
                                            onClick={() => {
                                                setOffset(
                                                    offset + pageSize,
                                                );
                                            }}
                                        >
                                            Next
                                        </button>

                                    </div>

                                </div>

                            </>

                        )}

                    </section>

                )}

                {view === "new" && (

                    <section className="panel">

                        <h2>New research job</h2>

                        <form onSubmit={createJob}>

                            <label htmlFor="topic">
                                Research topic
                            </label>

                            <input
                                id="topic"
                                value={topic}
                                maxLength={1000}
                                onChange={(event) => {
                                    setTopic(
                                        event.target.value,
                                    );
                                }}
                                required
                            />

                            <label htmlFor="scope">
                                Research scope
                            </label>

                            <textarea
                                id="scope"
                                rows={5}
                                value={scope}
                                onChange={(event) => {
                                    setScope(
                                        event.target.value,
                                    );
                                }}
                            />

                            <div className="button-group">

                                <button
                                    type="submit"
                                    className="button primary"
                                    disabled={saving}
                                >
                                    {saving
                                        ? "Creating..."
                                        : "Create draft"}
                                </button>

                                <button
                                    type="button"
                                    className="button secondary"
                                    onClick={returnToDashboard}
                                    disabled={saving}
                                >
                                    Cancel
                                </button>

                            </div>

                        </form>

                    </section>

                )}

                {view === "details" && selectedJob && (

                    <>

                        <section className="panel">

                            <div className="section-header">

                                <div>
                                    <h2>Research job</h2>

                                    <span
                                        className={
                                            "status " +
                                            selectedJob.status
                                        }
                                    >
                                        {selectedJob.status}
                                    </span>
                                </div>

                                <button
                                    type="button"
                                    className="button secondary"
                                    onClick={() => {
                                        void openJob(
                                            selectedJob.id,
                                        );
                                    }}
                                    disabled={saving || loading}
                                >
                                    Refresh
                                </button>

                            </div>

                            <form onSubmit={saveJob}>

                                <label htmlFor="topic">
                                    Research topic
                                </label>

                                <input
                                    id="topic"
                                    value={topic}
                                    maxLength={1000}
                                    disabled={!isDraft || saving}
                                    onChange={(event) => {
                                        setTopic(
                                            event.target.value,
                                        );
                                    }}
                                    required
                                />

                                <label htmlFor="scope">
                                    Research scope
                                </label>

                                <textarea
                                    id="scope"
                                    rows={5}
                                    value={scope}
                                    disabled={!isDraft || saving}
                                    onChange={(event) => {
                                        setScope(
                                            event.target.value,
                                        );
                                    }}
                                />

                                {isDraft && (

                                    <button
                                        type="submit"
                                        className="button primary"
                                        disabled={saving}
                                    >
                                        Save changes
                                    </button>

                                )}

                            </form>

                            <div className="job-metadata">

                                <p>
                                    <strong>Job ID:</strong>
                                    {" "}
                                    {selectedJob.id}
                                </p>

                                <p>
                                    <strong>Created:</strong>
                                    {" "}
                                    {formatDate(
                                        selectedJob.created_at,
                                    )}
                                </p>

                                <p>
                                    <strong>Submitted:</strong>
                                    {" "}
                                    {formatDate(
                                        selectedJob.submitted_at,
                                    )}
                                </p>

                                <p>
                                    <strong>Session ID:</strong>
                                    {" "}
                                    {selectedJob.research_session_id
                                        ?? "Not assigned"}
                                </p>

                            </div>

                            {pausePending && (

                                <p
                                    className="muted"
                                    role="status"
                                >
                                    Pause requested. Waiting for the
                                    research workflow to reach a safe
                                    checkpoint.
                                </p>

                            )}

                            {canPause && (

                                <div className="button-group">

                                    <button
                                        type="button"
                                        className="button secondary"
                                        disabled={
                                            saving ||
                                            loading ||
                                            pausePending
                                        }
                                        onClick={() => {
                                            void pauseJob();
                                        }}
                                    >
                                        {pausePending
                                            ? "Pause requested"
                                            : saving
                                                ? "Processing..."
                                                : "Pause research"}
                                    </button>

                                </div>

                            )}

                            {canResume && (

                                <div className="button-group">

                                    <button
                                        type="button"
                                        className="button primary"
                                        disabled={saving || loading}
                                        onClick={() => {
                                            void resumeJob();
                                        }}
                                    >
                                        {saving
                                            ? "Processing..."
                                            : "Resume research"}
                                    </button>

                                </div>

                            )}

                        </section>

                        <section className="panel">

                            <h2>Research questions</h2>

                            {selectedJob.questions.length === 0 && (

                                <p className="muted">
                                    No questions have been added.
                                </p>

                            )}

                            <div className="question-list">

                                {selectedJob.questions.map(
                                    (question) => (

                                        <div
                                            className="question-item"
                                            key={question.id}
                                        >

                                            <p>
                                                {question.question}
                                            </p>

                                            {isDraft && (

                                                <button
                                                    type="button"
                                                    className="button danger small"
                                                    disabled={saving}
                                                    onClick={() => {
                                                        void removeQuestion(
                                                            question.id,
                                                        );
                                                    }}
                                                >
                                                    Remove
                                                </button>

                                            )}

                                        </div>

                                    ),
                                )}

                            </div>

                            {isDraft && (

                                <form onSubmit={addQuestion}>

                                    <label htmlFor="new-question">
                                        Add research question
                                    </label>

                                    <textarea
                                        id="new-question"
                                        rows={3}
                                        maxLength={2000}
                                        value={newQuestion}
                                        disabled={saving}
                                        onChange={(event) => {
                                            setNewQuestion(
                                                event.target.value,
                                            );
                                        }}
                                    />

                                    <button
                                        type="submit"
                                        className="button secondary"
                                        disabled={
                                            saving ||
                                            !newQuestion.trim()
                                        }
                                    >
                                        Add question
                                    </button>

                                </form>

                            )}

                        </section>

                        {isDraft && (

                            <section className="panel submit-panel">

                                <div>
                                    <h2>Submit research</h2>

                                    <p>
                                        Submission locks the draft
                                        and places the job in the queue.
                                    </p>
                                </div>

                                <button
                                    type="button"
                                    className="button primary"
                                    disabled={saving}
                                    onClick={() => {
                                        void submitJob();
                                    }}
                                >
                                    Submit research job
                                </button>

                            </section>

                        )}

                    </>

                )}

            </main>

        </div>
    );
}


export default App;
