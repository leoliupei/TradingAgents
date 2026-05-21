import type { OptionsPayload, RunEvent, RunInfo, RunSpec } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE || "";

function previewText(value: string): string {
  return value.replace(/\s+/g, " ").slice(0, 160);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {})
    },
    ...init
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${previewText(text)}`);
  }
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    const text = await response.text();
    throw new Error(`Expected JSON from ${path}, got ${contentType || "unknown"}: ${previewText(text)}`);
  }
  return response.json() as Promise<T>;
}

export function fetchOptions(): Promise<OptionsPayload> {
  return request<OptionsPayload>("/api/options");
}

export function listRuns(): Promise<RunInfo[]> {
  return request<RunInfo[]>("/api/runs");
}

export function createRun(payload: RunSpec): Promise<RunInfo> {
  return request<RunInfo>("/api/runs", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function getRun(runId: string): Promise<RunInfo> {
  return request<RunInfo>(`/api/runs/${runId}`);
}

export function getEvents(
  runId: string,
  after = 0
): Promise<{ events: RunEvent[]; next: number }> {
  return request<{ events: RunEvent[]; next: number }>(
    `/api/events?run_id=${encodeURIComponent(runId)}&after=${after}`
  );
}

export function cancelRun(runId: string): Promise<RunInfo> {
  return request<RunInfo>(`/api/runs/${runId}/cancel`, { method: "POST" });
}

export function listReports(runId: string): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>(`/api/runs/${runId}/reports`);
}

export async function getReport(runId: string, section: string): Promise<string> {
  const response = await fetch(
    `${API_BASE}/api/report?run_id=${encodeURIComponent(runId)}&section=${encodeURIComponent(section)}`
  );
  if (!response.ok) {
    if (response.status === 404) {
      return "";
    }
    throw new Error(`${response.status} ${response.statusText}: ${previewText(await response.text())}`);
  }
  return response.text();
}

export function streamRun(
  runId: string,
  after: number,
  onEvent: (event: RunEvent) => void
): EventSource {
  const source = new EventSource(
    `${API_BASE}/api/stream?run_id=${encodeURIComponent(runId)}&after=${after}`
  );
  source.onmessage = (message) => onEvent(JSON.parse(message.data) as RunEvent);
  [
    "run_created",
    "process_started",
    "run_started",
    "graph_ready",
    "message",
    "tool_call",
    "report_updated",
    "decision_updated",
    "run_completed",
    "run_canceled",
    "error"
  ].forEach((type) => {
    source.addEventListener(type, (message) => {
      onEvent(JSON.parse((message as MessageEvent).data) as RunEvent);
    });
  });
  return source;
}
