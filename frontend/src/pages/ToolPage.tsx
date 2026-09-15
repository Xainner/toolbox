import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, Link, Navigate } from "react-router-dom";
import { z } from "zod";
import { motion, useReducedMotion } from "motion/react";
import { ArrowLeft, Download, Loader2, PlayCircle, Settings2 } from "lucide-react";
import { toast } from "sonner";
import { useTools } from "@/App";
import type { Artifact, JobStatus, ToolMeta, ToolOption } from "@/lib/types";
import { toolIcon } from "@/lib/types";
import FileDropzone, { formatBytes, type DropzoneFile } from "@/components/FileDropzone";
import ImageCompare from "@/components/ImageCompare";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Progress } from "@/components/ui/progress";
import { enqueueTool, waitForJob } from "@/lib/api";

const PdfOrganizer = lazy(() => import("@/components/PdfOrganizer"));
const MaskEditor = lazy(() => import("@/components/MaskEditor"));

export function buildSchema(tool: ToolMeta) {
  const shape: Record<string, z.ZodTypeAny> = {};
  for (const opt of tool.options) {
    if (opt.type === "number" || opt.type === "range") {
      let number = z.coerce.number({ message: "Indica un número válido" });
      if (opt.min !== undefined) number = number.min(opt.min, `Mínimo ${opt.min}`);
      if (opt.max !== undefined) number = number.max(opt.max, `Máximo ${opt.max}`);
      shape[opt.name] = number;
    } else if (opt.type === "switch") shape[opt.name] = z.boolean();
    else if (opt.type === "select") shape[opt.name] = z.string().min(1, "Elige una opción");
    else shape[opt.name] = z.string();
  }
  return z.object(shape);
}

export function defaultValues(tool: ToolMeta): Record<string, unknown> {
  return Object.fromEntries(tool.options.map((opt) => [opt.name,
    opt.type === "switch" ? Boolean(opt.default) :
      opt.default !== undefined && opt.default !== "" ? opt.default :
        opt.type === "select" ? opt.choices?.[0]?.value ?? "" : ""]));
}

export function isVisible(opt: ToolOption, values: Record<string, unknown>) {
  return !opt.visible_when || values[opt.visible_when.name] === opt.visible_when.equals;
}

function OptionField({ opt, value, onChange, disabled, error }: {
  opt: ToolOption; value: unknown; onChange: (value: unknown) => void; disabled: boolean; error?: string;
}) {
  if (opt.type === "switch") {
    return (
      <div className="flex items-start justify-between gap-4 rounded-lg border bg-card px-3 py-3">
        <div className="min-w-0">
          <Label htmlFor={opt.name} className="cursor-pointer leading-tight">{opt.label}</Label>
          {opt.help && <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{opt.help}</p>}
        </div>
        <Switch id={opt.name} className="mt-0.5 shrink-0" checked={Boolean(value)} onCheckedChange={onChange} disabled={disabled} />
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={opt.name}>{opt.label}</Label>
      {opt.type === "select" ? (
        <Select value={String(value ?? "")} onValueChange={onChange} disabled={disabled}>
          <SelectTrigger id={opt.name} aria-invalid={Boolean(error)}><SelectValue placeholder="Elegir…" /></SelectTrigger>
          <SelectContent>{(opt.choices ?? []).map((choice) => <SelectItem key={choice.value} value={choice.value}>{choice.label}</SelectItem>)}</SelectContent>
        </Select>
      ) : opt.type === "range" || opt.control === "range" ? (
        <div className="flex items-center gap-3"><input id={opt.name} type="range" className="w-full accent-[var(--brand)]"
          value={Number(value ?? opt.min ?? 0)} min={opt.min} max={opt.max} step={opt.step ?? 1}
          onChange={(event) => onChange(event.target.value)} disabled={disabled} /><output className="w-10 text-right text-sm">{String(value)}</output></div>
      ) : opt.type === "color" || opt.control === "color" ? (
        <div className="flex gap-2"><Input id={opt.name} type="color" className="h-10 w-14 cursor-pointer p-1" value={String(value || "#ffffff")}
          onChange={(event) => onChange(event.target.value)} disabled={disabled} /><Input value={String(value || "#ffffff")}
          onChange={(event) => onChange(event.target.value)} disabled={disabled} aria-label={`${opt.label} hexadecimal`} /></div>
      ) : (
        <Input id={opt.name} type={opt.type === "number" ? "number" : "text"} value={String(value ?? "")}
          min={opt.min} max={opt.max} step={opt.step ?? 1} placeholder={opt.placeholder}
          onChange={(event) => onChange(event.target.value)} disabled={disabled} aria-invalid={Boolean(error)} />
      )}
      {error ? <p className="text-xs text-destructive" role="alert">{error}</p> : opt.help ? <p className="text-xs text-muted-foreground">{opt.help}</p> : null}
    </div>
  );
}

export function OptionFields({ options, values, onChange, disabled, errors }: {
  options: ToolOption[]; values: Record<string, unknown>; onChange: (name: string, value: unknown) => void;
  disabled: boolean; errors: Record<string, { message?: string } | undefined>;
}) {
  const [advanced, setAdvanced] = useState(false);
  const regular = options.filter((opt) => !opt.advanced && isVisible(opt, values));
  const advancedFields = options.filter((opt) => opt.advanced && isVisible(opt, values));
  if (!options.length) return <p className="text-sm text-muted-foreground">Esta herramienta no necesita ajustes.</p>;
  const render = (opt: ToolOption) => <OptionField key={opt.name} opt={opt} value={values[opt.name]}
    onChange={(value) => onChange(opt.name, value)} disabled={disabled} error={errors[opt.name]?.message} />;
  return (
    <div className="flex flex-col gap-4">
      {regular.map(render)}
      {advancedFields.length > 0 && <>
        <Button type="button" variant="ghost" size="sm" className="justify-start px-0" onClick={() => setAdvanced((value) => !value)}>
          <Settings2 className="size-4" /> {advanced ? "Ocultar ajustes avanzados" : "Ajustes avanzados"}
        </Button>
        {advanced && <div className="flex flex-col gap-4 border-l-2 border-brand/30 pl-3">{advancedFields.map(render)}</div>}
      </>}
    </div>
  );
}

export default function ToolPage() {
  const { toolId } = useParams();
  const { tools, loading } = useTools();
  const tool = tools.find((item) => item.id === toolId);
  const reduceMotion = useReducedMotion();
  const [files, setFiles] = useState<DropzoneFile[]>([]);
  const [running, setRunning] = useState(false);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [result, setResult] = useState<JobStatus | null>(null);
  const [specialOptions, setSpecialOptions] = useState<Record<string, unknown>>({});
  const [composed, setComposed] = useState<Artifact | null>(null);
  const [beforeUrl, setBeforeUrl] = useState<string | null>(null);
  const pickerRef = useRef<(() => void) | null>(null);
  const schema = useMemo(() => tool ? buildSchema(tool) : z.object({}), [tool]);
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [valuesToolId, setValuesToolId] = useState<string | undefined>();
  const [formErrors, setFormErrors] = useState<Record<string, { message?: string }>>({});

  if (tool && valuesToolId !== tool.id) {
    setValuesToolId(tool.id);
    setValues(defaultValues(tool));
  }

  useEffect(() => {
    if (tool) {
      setFormErrors({});
      setFiles([]); setResult(null); setJob(null); setSpecialOptions({}); setComposed(null);
    }
  }, [tool?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!files[0] || !files[0].file.type.startsWith("image/")) { setBeforeUrl(null); return; }
    const url = URL.createObjectURL(files[0].file);
    setBeforeUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [files]);

  const setPages = useCallback((pages: Array<{ index: number; rotation: number }>) => setSpecialOptions({ pages }), []);

  if (!loading && !tool) return <Navigate to="/" replace />;
  if (!tool) return <div className="mx-auto max-w-7xl px-4 py-16 text-center text-muted-foreground">Cargando herramienta…</div>;
  const Icon = toolIcon(tool.icon);

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    const parsed = schema.safeParse(values);
    if (!parsed.success) {
      const next: Record<string, { message?: string }> = {};
      for (const issue of parsed.error.issues) next[String(issue.path[0])] = { message: issue.message };
      setFormErrors(next);
      return;
    }
    setFormErrors({});
    const formValues = parsed.data;
    if (!files.length) { toast.info("Primero agrega archivos"); pickerRef.current?.(); return; }
    setRunning(true); setResult(null); setComposed(null);
    try {
      const opts: Record<string, unknown> = { ...formValues, ...specialOptions };
      for (const option of tool.options) if (option.type === "number" || option.type === "range") opts[option.name] = Number(opts[option.name]);
      const queued = await enqueueTool(tool.id, files.map((file) => file.file), opts);
      setJob(queued);
      const completed = await waitForJob(queued.job_id, setJob);
      setResult(completed);
      toast.success("Resultado listo", { description: `${completed.output_name} · ${formatBytes(completed.output_size ?? 0)}` });
    } catch (error) {
      toast.error("Falló el procesamiento", { description: error instanceof Error ? error.message : String(error) });
    } finally { setRunning(false); }
  };

  const totalSize = files.reduce((sum, item) => sum + item.file.size, 0);
  const resultArtifact = composed ?? result?.artifacts?.find((artifact) => artifact.kind === "result" && artifact.mime.startsWith("image/"));
  const maskArtifact = result?.artifacts?.find((artifact) => artifact.kind === "mask");

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:py-10">
      <Link to="/" className="mb-6 inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground">
        <ArrowLeft className="size-4" /> Todas las herramientas
      </Link>
      <motion.div initial={reduceMotion ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
        <div className="flex items-start gap-4">
          <span className="grid size-12 shrink-0 place-items-center rounded-xl bg-brand text-brand-foreground shadow-md"><Icon className="size-6" /></span>
          <div><h1 className="flex flex-wrap items-center gap-2 text-2xl font-bold tracking-tight">{tool.name}
            <Badge variant="brand" className="uppercase">{tool.category}</Badge>{tool.ai && <Badge variant="outline">IA local</Badge>}</h1>
            <p className="mt-1 text-muted-foreground">{tool.description}</p></div>
        </div>

        <form onSubmit={onSubmit} className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
          <Card className="gap-4 py-5">
            <div className="flex items-center justify-between px-5"><h2 className="font-semibold">Archivos</h2>
              {files.length > 0 && <span className="text-xs text-muted-foreground">{files.length} archivo{files.length > 1 ? "s" : ""} · {formatBytes(totalSize)}</span>}</div>
            <div className="px-5"><FileDropzone files={files} onChange={(next) => { setFiles(next); setResult(null); setComposed(null); }}
              accept={tool.accept} multiple={tool.multiple} disabled={running} registerPicker={(open) => { pickerRef.current = open; }} />
              {tool.ui_mode === "pdf_organizer" && files[0] && <Suspense fallback={<p className="p-6 text-center text-sm text-muted-foreground">Cargando editor PDF…</p>}>
                <PdfOrganizer file={files[0].file} onChange={setPages} /></Suspense>}
            </div>
          </Card>
          <Card className="h-fit gap-4 py-5 lg:sticky lg:top-20">
            <h2 className="px-5 font-semibold">Opciones</h2>
            <div className="px-5"><OptionFields options={tool.options} values={values}
              onChange={(name, value) => setValues((current) => ({ ...current, [name]: value }))} disabled={running}
              errors={formErrors} /></div>
            <div className="mt-auto px-5"><Button type="submit" variant="brand" size="lg" className="w-full" disabled={running}>
              {running ? <><Loader2 className="size-4 animate-spin" /> Procesando…</> : files.length ? <><PlayCircle className="size-5" /> Ejecutar</> : <><PlayCircle className="size-5" /> Elegir archivos</>}
            </Button></div>
          </Card>
        </form>

        {running && job && <div className="mt-6 rounded-xl border bg-card p-4" role="status" aria-live="polite">
          <div className="mb-2 flex justify-between text-sm"><span>{job.stage || "Procesando"}</span><span className="text-muted-foreground">{job.progress}%</span></div>
          <Progress value={job.progress} /><p className="mt-2 text-xs text-muted-foreground">Puedes dejar esta pestaña abierta; el trabajo continúa en el servidor.</p>
        </div>}

        {result && <motion.section initial={reduceMotion ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="mt-6">
          <Card className="border-brand/40 py-5"><div className="flex flex-col items-start justify-between gap-4 px-5 sm:flex-row sm:items-center">
            <div><h2 className="flex items-center gap-2 font-semibold">Resultado listo <Badge variant="brand">OK</Badge></h2>
              <p className="mt-1 text-sm text-muted-foreground">{result.output_name} · {formatBytes(result.output_size ?? 0)}
                {result.input_size ? ` · entrada ${formatBytes(result.input_size)}` : ""}{result.duration_ms ? ` · ${(result.duration_ms / 1000).toFixed(1)}s` : ""}</p></div>
            <Button variant="brand" asChild><a href={composed?.url ?? result.download_url ?? `/api/download/${result.job_id}`} download={composed?.name ?? result.output_name}>
              <Download className="size-4" /> Descargar</a></Button></div>
            {result.artifacts?.filter((artifact) => artifact.kind === "sidecar").map((artifact) => <div key={artifact.id} className="mx-5 mt-3 text-sm">
              <a className="text-brand underline-offset-4 hover:underline" href={artifact.url} download>{artifact.name}</a></div>)}
          </Card>
          {beforeUrl && resultArtifact && <Card className="mt-6 p-4"><h2 className="mb-4 font-semibold">Antes y después</h2>
            <ImageCompare before={beforeUrl} after={`${resultArtifact.url}?v=${composed ? Date.now() : 0}`} /></Card>}
          {tool.ui_mode === "mask_editor" && maskArtifact && files[0] && <Suspense fallback={<p className="p-6 text-center text-sm text-muted-foreground">Cargando editor de máscara…</p>}>
            <MaskEditor sourceFile={files[0].file} maskUrl={maskArtifact.url} jobId={result.job_id}
              background={String(values.post ?? "transparent")} color={String(values.color ?? "#ffffff")} onComposed={setComposed} />
          </Suspense>}
        </motion.section>}
      </motion.div>
    </div>
  );
}
