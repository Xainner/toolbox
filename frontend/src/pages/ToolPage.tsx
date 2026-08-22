import { useMemo, useState } from "react";
import { useParams, Link, Navigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { motion } from "motion/react";
import { ArrowLeft, Download, Loader2, PlayCircle } from "lucide-react";
import { toast } from "sonner";
import { useTools } from "@/App";
import type { ToolMeta, ToolOption } from "@/lib/types";
import { toolIcon } from "@/lib/types";
import FileDropzone, { formatBytes, type DropzoneFile } from "@/components/FileDropzone";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Progress } from "@/components/ui/progress";
import { runTool, downloadResult, type JobResult } from "@/lib/api";

function buildSchema(tool: ToolMeta) {
  const shape: Record<string, z.ZodTypeAny> = {};
  for (const opt of tool.options) {
    switch (opt.type) {
      case "number": {
        let num = z.coerce.number();
        if (opt.min !== undefined) num = num.min(opt.min);
        if (opt.max !== undefined) num = num.max(opt.max);
        shape[opt.name] = num;
        break;
      }
      case "switch":
        shape[opt.name] = z.boolean();
        break;
      case "select":
        shape[opt.name] = z.string().min(1);
        break;
      default:
        shape[opt.name] = z.string();
    }
  }
  return z.object(shape);
}

function defaultValues(tool: ToolMeta): Record<string, unknown> {
  const vals: Record<string, unknown> = {};
  for (const opt of tool.options) {
    if (opt.type === "switch") vals[opt.name] = Boolean(opt.default);
    else if (opt.default !== undefined && opt.default !== "") vals[opt.name] = opt.default;
    else if (opt.type === "select") vals[opt.name] = opt.choices?.[0]?.value ?? "";
    else vals[opt.name] = "";
  }
  return vals;
}

function OptionField({
  opt,
  value,
  onChange,
  disabled,
}: {
  opt: ToolOption;
  value: unknown;
  onChange: (v: unknown) => void;
  disabled: boolean;
}) {
  if (opt.type === "switch") {
    return (
      <div className="flex items-center justify-between rounded-lg border bg-card px-3 py-2.5">
        <Label htmlFor={opt.name} className="cursor-pointer">
          {opt.label}
          {opt.help && <span className="ml-2 text-xs font-normal text-muted-foreground">{opt.help}</span>}
        </Label>
        <Switch id={opt.name} checked={Boolean(value)} onCheckedChange={(v) => onChange(v)} disabled={disabled} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={opt.name}>{opt.label}</Label>
      {opt.type === "select" ? (
        <Select value={String(value ?? "")} onValueChange={(v) => onChange(v)} disabled={disabled}>
          <SelectTrigger id={opt.name}>
            <SelectValue placeholder="Elegir…" />
          </SelectTrigger>
          <SelectContent>
            {(opt.choices ?? []).map((c) => (
              <SelectItem key={c.value} value={c.value}>
                {c.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      ) : opt.type === "number" ? (
        <Input
          id={opt.name}
          type="number"
          value={String(value ?? "")}
          min={opt.min}
          max={opt.max}
          step={opt.step ?? 1}
          placeholder={opt.placeholder}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
        />
      ) : (
        <Input
          id={opt.name}
          type="text"
          value={String(value ?? "")}
          placeholder={opt.placeholder}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
        />
      )}
      {opt.help && <p className="text-xs text-muted-foreground">{opt.help}</p>}
    </div>
  );
}

export function OptionFields({
  options,
  values,
  onChange,
  disabled,
}: {
  options: ToolOption[];
  values: Record<string, unknown>;
  onChange: (name: string, v: unknown) => void;
  disabled: boolean;
}) {
  if (options.length === 0) return null;
  return (
    <div className="flex flex-col gap-4">
      {options.map((opt) => (
        <OptionField
          key={opt.name}
          opt={opt}
          value={values[opt.name]}
          onChange={(v) => onChange(opt.name, v)}
          disabled={disabled}
        />
      ))}
    </div>
  );
}

export default function ToolPage() {
  const { toolId } = useParams();
  const { tools, loading } = useTools();
  const tool = tools.find((t) => t.id === toolId);

  const [files, setFiles] = useState<DropzoneFile[]>([]);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<JobResult | null>(null);

  const schema = useMemo(() => (tool ? buildSchema(tool) : z.object({})), [tool]);
  const form = useForm<Record<string, unknown>>({
    resolver: zodResolver(schema as never),
    defaultValues: useMemo(() => (tool ? defaultValues(tool) : {}), [tool]),
  });

  if (!loading && !tool) return <Navigate to="/" replace />;

  if (!tool) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-16 text-center text-muted-foreground">Cargando herramienta…</div>
    );
  }

  const Icon = toolIcon(tool.icon);

  const onSubmit = form.handleSubmit(async (values) => {
    if (files.length === 0) {
      toast.error("Agrega al menos un archivo");
      return;
    }
    setRunning(true);
    setResult(null);
    try {
      // coerce numbers antes de enviar
      const opts: Record<string, unknown> = { ...values };
      for (const o of tool.options) {
        if (o.type === "number") opts[o.name] = Number(opts[o.name]);
      }
      const res = await runTool(tool.id, files.map((f) => f.file), opts);
      setResult(res);
      toast.success("Listo", {
        description: `${res.output_name} · ${formatBytes(res.output_size)}${
          res.duration_ms ? ` · ${(res.duration_ms / 1000).toFixed(1)}s` : ""
        }`,
      });
    } catch (e) {
      toast.error("Falló el procesamiento", { description: e instanceof Error ? e.message : String(e) });
    } finally {
      setRunning(false);
    }
  });

  const totalSize = files.reduce((a, f) => a + f.file.size, 0);

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <Link to="/" className="mb-6 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> Todas las herramientas
      </Link>

      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
        <div className="flex items-start gap-4">
          <span className="grid size-12 shrink-0 place-items-center rounded-xl bg-brand text-brand-foreground shadow-md">
            <Icon className="size-6" />
          </span>
          <div>
            <h1 className="flex items-center gap-3 text-2xl font-bold tracking-tight">
              {tool.name} <Badge variant="brand" className="uppercase">{tool.category}</Badge>
            </h1>
            <p className="mt-1 text-muted-foreground">{tool.description}</p>
          </div>
        </div>

        <form onSubmit={onSubmit} className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-[1fr_300px]">
          <Card className="gap-4 py-5">
            <div className="flex items-center justify-between px-5">
              <h2 className="font-semibold">Archivos</h2>
              {files.length > 0 && (
                <span className="text-xs text-muted-foreground">
                  {files.length} archivo{files.length > 1 ? "s" : ""} · {formatBytes(totalSize)}
                </span>
              )}
            </div>
            <div className="px-5">
              <FileDropzone
                files={files}
                onChange={(f) => {
                  setFiles(f);
                  if (result) setResult(null);
                }}
                accept={tool.accept}
                multiple={tool.multiple}
                disabled={running}
              />
            </div>
          </Card>

          <Card className="h-fit gap-4 py-5">
            <h2 className="px-5 font-semibold">Opciones</h2>
            <div className="px-5">
              <OptionFields
                options={tool.options}
                values={form.watch()}
                onChange={(name, v) => form.setValue(name, v as never, { shouldValidate: true })}
                disabled={running}
              />
            </div>
            <div className="mt-auto px-5">
              <Button type="submit" variant="brand" size="lg" className="w-full" disabled={running || files.length === 0}>
                {running ? (
                  <>
                    <Loader2 className="size-4 animate-spin" /> Procesando…
                  </>
                ) : (
                  <>
                    <PlayCircle className="size-5" /> Ejecutar
                  </>
                )}
              </Button>
            </div>
          </Card>
        </form>

        {running && (
          <div className="mt-6 flex flex-col gap-2">
            <Progress value={66} />
            <p className="text-xs text-muted-foreground">Procesando en el servidor…</p>
          </div>
        )}

        {result && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
            <Card className="mt-6 border-brand/40 py-5">
              <div className="flex flex-col items-start justify-between gap-4 px-5 sm:flex-row sm:items-center">
                <div>
                  <h2 className="flex items-center gap-2 font-semibold">
                    Resultado listo
                    <Badge variant="brand">✓</Badge>
                  </h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {result.output_name} · {formatBytes(result.output_size)}
                    {result.input_size ? ` (antes ${formatBytes(result.input_size)})` : ""}
                    {result.duration_ms ? ` · ${(result.duration_ms / 1000).toFixed(1)}s` : ""}
                  </p>
                </div>
                <Button
                  variant="brand"
                  onClick={() =>
                    downloadResult(result.job_id, result.output_name).catch((e) =>
                      toast.error("Error al descargar", { description: String(e) })
                    )
                  }
                >
                  <Download className="size-4" /> Descargar
                </Button>
              </div>
            </Card>
          </motion.div>
        )}
      </motion.div>
    </div>
  );
}
