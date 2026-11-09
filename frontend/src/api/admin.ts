
import {
    request,
} from "./client";


export interface AdminUser {

    id: string;
    username: string;
    email: string | null;
    role: string;
    is_active: boolean;
    approval_status: string;
    must_change_password: boolean;
    created_at: string;
    approved_at: string | null;
    last_login_at: string | null;
}


export interface AdminUserList {

    items: AdminUser[];
    total: number;
    limit: number;
    offset: number;
}


export interface AdminAction {

    id: string;
    approval_status: string;
    message: string;
}


export async function listAdminUsers(
    approvalStatus: string | null = null,
    limit: number = 50,
    offset: number = 0,
): Promise<AdminUserList> {

    const parameters = new URLSearchParams({
        limit: String(limit),
        offset: String(offset),
    });

    if (approvalStatus !== null) {

        parameters.set(
            "approval_status",
            approvalStatus,
        );
    }

    return await request<AdminUserList>(
        `/api/admin/users?${parameters.toString()}`,
    );
}


export async function approveUser(
    userId: string,
): Promise<AdminAction> {

    return await request<AdminAction>(
        `/api/admin/users/${encodeURIComponent(userId)}/approve`,
        {
            method: "POST",
        },
    );
}


export async function rejectUser(
    userId: string,
): Promise<AdminAction> {

    return await request<AdminAction>(
        `/api/admin/users/${encodeURIComponent(userId)}/reject`,
        {
            method: "POST",
        },
    );
}


export async function enableUser(
    userId: string,
): Promise<AdminAction> {

    return await request<AdminAction>(
        `/api/admin/users/${encodeURIComponent(userId)}/enable`,
        {
            method: "POST",
        },
    );
}


export async function disableUser(
    userId: string,
): Promise<AdminAction> {

    return await request<AdminAction>(
        `/api/admin/users/${encodeURIComponent(userId)}/disable`,
        {
            method: "POST",
        },
    );
}

export interface AdminResearchJob {

    id: string;
    user_id: string;
    username: string;
    topic: string;
    scope: string | null;
    status: string;
    research_session_id: string | null;
    created_at: string;
    submitted_at: string | null;
    started_at: string | null;
    completed_at: string | null;
    last_error: string | null;
    execution_owner: string | null;
    lease_expires_at: string | null;
}


export interface AdminResearchJobList {

    items: AdminResearchJob[];
    total: number;
    limit: number;
    offset: number;
}


export interface AdminResearchJobStatusCount {

    status: string;
    count: number;
}


export interface AdminResearchJobSummary {

    total: number;
    statuses: AdminResearchJobStatusCount[];
}


export async function listAdminResearchJobs(
    jobStatus: string | null = null,
    limit: number = 50,
    offset: number = 0,
    signal?: AbortSignal,
): Promise<AdminResearchJobList> {

    const parameters = new URLSearchParams({
        limit: String(limit),
        offset: String(offset),
    });

    if (jobStatus !== null) {

        parameters.set(
            "job_status",
            jobStatus,
        );
    }

    return await request<AdminResearchJobList>(
        `/api/admin/research/jobs?${parameters.toString()}`,
        {
            signal,
        },
    );
}


export async function getAdminResearchJobSummary(
    signal?: AbortSignal,
): Promise<AdminResearchJobSummary> {

    return await request<AdminResearchJobSummary>(
        "/api/admin/research/jobs/summary",
        {
            signal,
        },
    );
}


export interface AdminRecoveryHealthSnapshot {

    state: string;
    pid: number;
    started_at: string;
    updated_at: string;
    last_cycle_at: string | null;
    last_success_at: string | null;
    last_cycle_duration_seconds: number | null;
    cycles: number;
    resumed: number;
    paused: number;
    skipped: number;
    failed_sessions: number;
    cycle_errors: number;
    last_error: string | null;
}


export interface AdminRecoveryHealthResponse {

    available: boolean;
    health: AdminRecoveryHealthSnapshot | null;
}


export async function getAdminRecoveryHealth(
    signal?: AbortSignal,
): Promise<AdminRecoveryHealthResponse> {

    return await request<AdminRecoveryHealthResponse>(
        "/api/admin/recovery/health",
        {
            signal,
        },
    );
}
