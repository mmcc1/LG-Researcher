
export interface ResearchQuestion {
    id: number;
    question: string;
    created_at: string;
}

export interface ResearchJobSummary {
    id: string;
    topic: string;
    scope: string | null;
    status: string;
    research_session_id: string | null;
    created_at: string;
    submitted_at: string | null;
    started_at: string | null;
    completed_at: string | null;
}

export interface ResearchJob extends ResearchJobSummary {
    questions: ResearchQuestion[];
}

export interface ResearchJobList {
    items: ResearchJobSummary[];
    total: number;
    limit: number;
    offset: number;
}

export interface ResearchJobInput {
    topic: string;
    scope: string | null;
}

export interface ResearchJobAction {
    id: string;
    status: string;
}

export interface AddedResearchQuestion {
    id: number;
    research_job_id: string;
    question: string;
}

export class ApiError extends Error {
    readonly status: number;

    constructor(
        status: number,
        message: string,
    ) {
        super(message);

        this.name = "ApiError";
        this.status = status;
    }
}

async function request<T>(
    path: string,
    options: RequestInit = {},
): Promise<T> {

    const headers = new Headers(
        options.headers,
    );

    if (options.body !== undefined) {
        headers.set(
            "Content-Type",
            "application/json",
        );
    }

    const response = await fetch(
        path,
        {
            ...options,
            headers,
        },
    );

    if (!response.ok) {

        let message = (
            `Request failed (${response.status}).`
        );

        try {

            const body: unknown = await response.json();

            if (
                typeof body === "object" &&
                body !== null &&
                "detail" in body
            ) {

                const detail = body.detail;

                if (typeof detail === "string") {
                    message = detail;
                }
            }

        } catch {
            // Retain the HTTP status message.
        }

        throw new ApiError(
            response.status,
            message,
        );
    }

    if (response.status === 204) {
        return undefined as T;
    }

    return await response.json() as T;
}

const basePath = "/api/research/jobs";

export async function listResearchJobs(
    limit: number,
    offset: number,
): Promise<ResearchJobList> {

    const parameters = new URLSearchParams({
        limit: String(limit),
        offset: String(offset),
    });

    return await request<ResearchJobList>(
        `${basePath}?${parameters.toString()}`,
    );
}

export async function getResearchJob(
    jobId: string,
): Promise<ResearchJob> {

    return await request<ResearchJob>(
        `${basePath}/${encodeURIComponent(jobId)}`,
    );
}

export async function createResearchJob(
    input: ResearchJobInput,
): Promise<ResearchJob> {

    return await request<ResearchJob>(
        basePath,
        {
            method: "POST",
            body: JSON.stringify(input),
        },
    );
}

export async function updateResearchJob(
    jobId: string,
    input: ResearchJobInput,
): Promise<ResearchJob> {

    return await request<ResearchJob>(
        `${basePath}/${encodeURIComponent(jobId)}`,
        {
            method: "PATCH",
            body: JSON.stringify(input),
        },
    );
}

export async function addResearchQuestion(
    jobId: string,
    question: string,
): Promise<AddedResearchQuestion> {

    return await request<AddedResearchQuestion>(
        `${basePath}/${encodeURIComponent(jobId)}/questions`,
        {
            method: "POST",
            body: JSON.stringify({
                question,
            }),
        },
    );
}

export async function removeResearchQuestion(
    jobId: string,
    questionId: number,
): Promise<void> {

    await request<void>(
        `${basePath}/${encodeURIComponent(jobId)}/questions/${questionId}`,
        {
            method: "DELETE",
        },
    );
}

export async function submitResearchJob(
    jobId: string,
): Promise<ResearchJobAction> {

    return await request<ResearchJobAction>(
        `${basePath}/${encodeURIComponent(jobId)}/submit`,
        {
            method: "POST",
        },
    );
}
