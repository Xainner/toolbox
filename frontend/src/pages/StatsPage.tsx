import { useEffect, useMemo, useState } from "react";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  createColumnHelper,
  type SortingState,
} from "@tanstack/react-table";
import { BarChart, Bar, XAxis, YAxis, Tooltip as ReTooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { ArrowUpDown, Activity } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useTools } from "@/App";

interface JobRow {
  id: number;
  tool_id: string;
  files: number;
  status: string;
  duration_ms: number | null;
  created_at: string;
}

const helper = createColumnHelper<JobRow>();

function timeAgo(iso: string): string {
  const s = Math.floor((Date.now() - new Date(iso + "Z").getTime()) / 1000);
  if (s < 60) return `hace ${s}s`;
  if (s < 3600) return `hace ${Math.floor(s / 60)} min`;
  if (s < 86400) return `hace ${Math.floor(s / 3600)} h`;
  return `hace ${Math.floor(s / 86400)} d`;
}

export default function StatsPage() {
  const [jobs, setJobs] = useState<JobRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [sorting, setSorting] = useState<SortingState>([{ id: "created_at", desc: true }]);
  const [loading, setLoading] = useState(true);
  const { tools } = useTools();
  const names = useMemo(() => new Map(tools.map((tool) => [tool.id, tool.name])), [tools]);

  useEffect(() => {
    fetch("/api/stats")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`Error ${r.status}`))))
      .then((j) => setJobs(j.jobs ?? []))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const columns = useMemo(
    () => [
      helper.accessor("tool_id", { header: "Herramienta", cell: (c) => <span className="font-medium">{names.get(c.getValue()) ?? c.getValue()}</span> }),
      helper.accessor("files", { header: "Archivos" }),
      helper.accessor("status", {
        header: "Estado",
        cell: (c) => (
          <Badge variant={["ok", "succeeded"].includes(c.getValue()) ? "brand" : c.getValue() === "failed" || c.getValue() === "error" ? "destructive" : "outline"}>
            {["ok", "succeeded"].includes(c.getValue()) ? "OK" : c.getValue()}
          </Badge>
        ),
      }),
      helper.accessor("duration_ms", {
        header: "Duración",
        cell: (c) => (c.getValue() != null ? `${(c.getValue()! / 1000).toFixed(1)}s` : "—"),
      }),
      helper.accessor("created_at", { header: "Cuándo", cell: (c) => timeAgo(c.getValue()) }),
    ],
    [names]
  );

  const table = useReactTable({
    data: jobs,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  const byTool = useMemo(() => {
    const counts = new Map<string, number>();
    for (const j of jobs) counts.set(j.tool_id, (counts.get(j.tool_id) ?? 0) + 1);
    return [...counts.entries()].map(([id, trabajos]) => ({ name: names.get(id) ?? id, trabajos })).sort((a, b) => b.trabajos - a.trabajos);
  }, [jobs, names]);

  const okCount = jobs.filter((j) => ["ok", "succeeded"].includes(j.status)).length;

  return (
    <div className="mx-auto max-w-7xl px-4 py-10">
      <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight">
        <Activity className="size-6 text-brand" /> Actividad
      </h1>
      <p className="mt-1 text-muted-foreground">Historial de trabajos procesados por el servidor.</p>

      {error && (
        <Card className="mt-6 border-destructive/40 p-4 text-sm text-destructive">API sin conexión: {error}</Card>
      )}

      {loading && <div className="mt-6 h-32 animate-pulse rounded-xl border bg-card" aria-label="Cargando actividad" />}

      {!error && !loading && (
        <>
          <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Card className="gap-1 py-4">
              <p className="px-5 text-xs text-muted-foreground uppercase">Trabajos</p>
              <p className="px-5 text-2xl font-bold">{jobs.length}</p>
            </Card>
            <Card className="gap-1 py-4">
              <p className="px-5 text-xs text-muted-foreground uppercase">Exitosos</p>
              <p className="px-5 text-2xl font-bold text-brand">{okCount}</p>
            </Card>
            <Card className="gap-1 py-4">
              <p className="px-5 text-xs text-muted-foreground uppercase">Herramientas usadas</p>
              <p className="px-5 text-2xl font-bold">{byTool.length}</p>
            </Card>
          </div>

          {byTool.length > 0 && (
            <Card className="mt-6 py-5">
              <h2 className="px-5 pb-2 font-semibold">Trabajos por herramienta</h2>
              <div className="h-56 px-2">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={byTool}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                    <XAxis dataKey="name" tick={{ fontSize: 12, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} width={28} />
                    <ReTooltip
                      cursor={{ fill: "var(--accent)" }}
                      contentStyle={{ background: "var(--popover)", border: "1px solid var(--border)", borderRadius: 8, color: "var(--popover-foreground)" }}
                    />
                    <Bar dataKey="trabajos" fill="var(--brand)" radius={[6, 6, 0, 0]} maxBarSize={48} isAnimationActive={false} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
          )}

          <Card className="mt-6 gap-0 overflow-x-auto py-0">
            <table className="min-w-[680px] w-full text-sm">
              <thead>
                {table.getHeaderGroups().map((hg) => (
                  <tr key={hg.id} className="border-b">
                    {hg.headers.map((h) => (
                      <th key={h.id} className="px-4 py-3 text-left font-medium text-muted-foreground">
                        <button
                          className="flex cursor-pointer items-center gap-1 hover:text-foreground"
                          onClick={h.column.getToggleSortingHandler()}
                        >
                          {flexRender(h.column.columnDef.header, h.getContext())}
                          <ArrowUpDown className="size-3" />
                        </button>
                      </th>
                    ))}
                  </tr>
                ))}
              </thead>
              <tbody>
                {table.getRowModel().rows.map((row) => (
                  <tr key={row.id} className="border-b last:border-0 hover:bg-accent/40">
                    {row.getVisibleCells().map((cell) => (
                      <td key={cell.id} className="px-4 py-2.5">
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                ))}
                {table.getRowModel().rows.length === 0 && (
                  <tr>
                    <td colSpan={columns.length} className="px-4 py-10 text-center text-muted-foreground">
                      Sin trabajos todavía — ejecuta una herramienta y aparecerá aquí.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </Card>
        </>
      )}
    </div>
  );
}
