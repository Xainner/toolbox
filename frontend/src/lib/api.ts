import type { Artifact, JobStatus, ToolMeta } from "./types";

const BASE = "/api";

export async function fetchTools(): Promise<ToolMeta[]> {
  const r = await fetch(`${BASE}/tools`);
  if (!r.ok) throw new Error("No se pudo cargar el catálogo de herramientas");
  const j = await r.json();
  return j.tools as ToolMeta[];
}

export interface JobResult {
  job_id: string;
  download_url: string;
  output_name: string;
  output_size: number;
  input_size?: number;
  duration_ms?: number;
  artifacts?: Artifact[];
}

async function apiError(r: Response) {
  let detail = `Error ${r.status}`;
  try { detail = (await r.json()).detail ?? detail; } catch { /* respuesta no JSON */ }
  return new Error(detail);
}

export async function enqueueTool(toolId: string, files: File[], options: Record<string, unknown>) {
  const fd = new FormData();
  for (const file of files) fd.append("files", file, file.name);
  fd.append("options", JSON.stringify(options ?? {}));
  const response = await fetch(`${BASE}/tools/${toolId}/jobs`, { method: "POST", body: fd });
  if (!response.ok) throw await apiError(response);
  return (await response.json()) as JobStatus;
}

export async function fetchJob(jobId: string): Promise<JobStatus> {
  const response = await fetch(`${BASE}/jobs/${jobId}`);
  if (!response.ok) throw await apiError(response);
  return response.json();
}

export async function waitForJob(jobId: string, onUpdate: (job: JobStatus) => void): Promise<JobStatus> {
  for (;;) {
    const job = await fetchJob(jobId);
    onUpdate(job);
    if (job.status === "succeeded") return job;
    if (job.status === "failed") throw new Error(job.error || "Falló el procesamiento");
    await new Promise((resolve) => setTimeout(resolve, 700));
  }
}

export async function composeMask(jobId: string, mask: Blob, background: string, color: string) {
  const data = new FormData();
  data.append("mask", mask, "mascara.png");
  data.append("background", background);
  data.append("color", color);
  const response = await fetch(`${BASE}/jobs/${jobId}/compose`, { method: "POST", body: data });
  if (!response.ok) throw await apiError(response);
  return (await response.json()).artifact as Artifact;
}

export async function runTool(
  toolId: string,
  files: File[],
  options: Record<string, unknown>,
): Promise<JobResult> {
  const fd = new FormData();
  for (const f of files) fd.append("files", f, f.name);
  fd.append("options", JSON.stringify(options ?? {}));
  const r = await fetch(`${BASE}/tools/${toolId}/run`, {
    method: "POST",
    body: fd,
  });
  if (!r.ok) {
    let detail = `Error ${r.status}`;
    try {
      const j = await r.json();
      detail = j.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return (await r.json()) as JobResult;
}

export async function downloadResult(jobId: string, name: string) {
  const r = await fetch(`${BASE}/download/${jobId}`);
  if (!r.ok) throw new Error("No se pudo descargar el resultado");
  const blob = await r.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
