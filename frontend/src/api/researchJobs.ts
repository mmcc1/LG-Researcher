
import {
    request,
} from "./client";

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


export async function pauseResearchJob(
    jobId: string,
): Promise<ResearchJobAction> {

    return await request<ResearchJobAction>(
        `${basePath}/${encodeURIComponent(jobId)}/pause`,
        {
            method: "POST",
        },
    );
}


export async function resumeResearchJob(
    jobId: string,
): Promise<ResearchJobAction> {

    return await request<ResearchJobAction>(
        `${basePath}/${encodeURIComponent(jobId)}/resume`,
        {
            method: "POST",
        },
    );
}