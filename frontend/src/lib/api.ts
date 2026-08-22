import type { ToolMeta } from "./types";

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
