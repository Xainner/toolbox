import { useDeferredValue, useState } from "react";
import { Link } from "react-router-dom";
import { motion, useReducedMotion } from "motion/react";
import { ArrowRight, Search, ShieldCheck, Cpu } from "lucide-react";
import { useTools } from "@/App";
import { toolIcon, type ToolMeta } from "@/lib/types";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

function ToolCard({ tool, index }: { tool: ToolMeta; index: number }) {
  const Icon = toolIcon(tool.icon);
  const reduceMotion = useReducedMotion();
  return (
    <motion.div
      initial={reduceMotion ? false : { opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: Math.min(index * 0.04, 0.4) }}
    >
      <Link to={`/tool/${tool.id}`} className="group block h-full">
        <Card className="h-full gap-3 py-5 transition-all group-hover:-translate-y-0.5 group-hover:border-brand/40 group-hover:shadow-lg group-hover:shadow-brand/5">
          <div className="flex items-start gap-3 px-5">
            <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-brand/10 text-brand transition-colors group-hover:bg-brand group-hover:text-brand-foreground">
              <Icon className="size-5" />
            </span>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h3 className="font-semibold leading-tight">{tool.name}</h3>
                <Badge variant="brand" className="uppercase">{tool.category}</Badge>
              </div>
              <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{tool.description}</p>
            </div>
          </div>
          <div className="mt-auto flex items-center gap-1 px-5 text-xs font-medium text-muted-foreground transition-colors group-hover:text-brand">
            Abrir herramienta <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-0.5" />
          </div>
        </Card>
      </Link>
    </motion.div>
  );
}

export default function Home() {
  const { tools, loading, error } = useTools();
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<"all" | "pdf" | "imagen">("all");
  const deferredQuery = useDeferredValue(query.trim().toLowerCase());

  const visible = tools.filter((tool) =>
    (category === "all" || tool.category === category) &&
    (!deferredQuery || `${tool.name} ${tool.description}`.toLowerCase().includes(deferredQuery))
  );

  const pdf = visible.filter((t) => t.category === "pdf");
  const img = visible.filter((t) => t.category === "imagen");

  const Section = ({ title, items }: { title: string; items: ToolMeta[] }) =>
    items.length > 0 ? (
      <section className="mt-10">
        <h2 className="mb-4 text-sm font-semibold tracking-wide text-muted-foreground uppercase">{title}</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {items.map((t, i) => (
            <ToolCard key={t.id} tool={t} index={i} />
          ))}
        </div>
      </section>
    ) : null;

  return (
    <div className="mx-auto max-w-7xl px-4 py-12">
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.25 }}>
        <h1 className="max-w-2xl text-4xl font-bold tracking-tight sm:text-5xl">
          Todas las herramientas,{" "}
          <span className="bg-gradient-to-r from-brand to-orange-400 bg-clip-text text-transparent">en un solo lugar</span>
        </h1>
        <p className="mt-4 max-w-xl text-muted-foreground">
          PDF e imágenes: une, divide, comprime, convierte, protege… y elimina fondos con IA.
          Self-hosted, rápido y sin subir nada a la nube de nadie más.
        </p>
        <div className="mt-5 flex flex-wrap gap-3 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1.5"><ShieldCheck className="size-4 text-brand" /> Archivos privados</span>
          <span className="inline-flex items-center gap-1.5"><Cpu className="size-4 text-brand" /> IA local CPU/GPU</span>
        </div>
      </motion.div>

      {!loading && !error && (
        <div className="mt-9 flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="relative max-w-xl flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input value={query} onChange={(event) => setQuery(event.target.value)}
              className="h-11 pl-9" placeholder="Buscar entre todas las herramientas…" aria-label="Buscar herramientas" />
          </div>
          <div className="flex gap-2" aria-label="Filtrar por categoría">
            {([['all','Todo'],['pdf','PDF'],['imagen','Imagen']] as const).map(([value, label]) => (
              <Button key={value} type="button" size="sm" variant={category === value ? "brand" : "outline"}
                onClick={() => setCategory(value)}>{label}</Button>
            ))}
          </div>
        </div>
      )}

      {loading && (
        <div className="mt-12 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-[118px] animate-pulse rounded-xl border bg-card" />
          ))}
        </div>
      )}

      {error && (
        <div className="mt-12 rounded-xl border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
          No se pudo conectar con la API: {error}. ¿Está corriendo el backend?
        </div>
      )}

      {!loading && !error && (
        <>
          <Section title="Organiza y optimiza PDF" items={pdf} />
          <Section title="Imagen" items={img} />
          {visible.length === 0 && <p className="mt-12 text-center text-sm text-muted-foreground">No encontramos herramientas con ese filtro.</p>}
        </>
      )}
    </div>
  );
}
