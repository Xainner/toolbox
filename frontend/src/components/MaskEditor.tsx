import { useCallback, useEffect, useRef, useState } from "react";
import { Eraser, Paintbrush, RotateCcw, RotateCw, Save } from "lucide-react";
import type { Artifact } from "@/lib/types";
import { composeMask } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function MaskEditor({ sourceFile, maskUrl, jobId, background, color, onComposed }: {
  sourceFile: File; maskUrl: string; jobId: string; background: string; color: string;
  onComposed: (artifact: Artifact) => void;
}) {
  const displayRef = useRef<HTMLCanvasElement>(null);
  const maskRef = useRef<HTMLCanvasElement>(document.createElement("canvas"));
  const sourceRef = useRef<HTMLImageElement | null>(null);
  const [mode, setMode] = useState<"restore" | "erase">("restore");
  const [brush, setBrush] = useState(36);
  const [zoom, setZoom] = useState(100);
  const [saving, setSaving] = useState(false);
  const [history, setHistory] = useState<ImageData[]>([]);
  const [future, setFuture] = useState<ImageData[]>([]);
  const drawing = useRef(false);

  const render = useCallback(() => {
    const canvas = displayRef.current;
    const source = sourceRef.current;
    if (!canvas || !source) return;
    const ctx = canvas.getContext("2d")!;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(source, 0, 0, canvas.width, canvas.height);
    ctx.globalCompositeOperation = "destination-in";
    ctx.drawImage(maskRef.current, 0, 0, canvas.width, canvas.height);
    ctx.globalCompositeOperation = "source-over";
  }, []);

  useEffect(() => {
    const sourceUrl = URL.createObjectURL(sourceFile);
    const source = new Image();
    const mask = new Image();
    source.onload = () => {
      sourceRef.current = source;
      const canvas = displayRef.current!;
      canvas.width = source.naturalWidth;
      canvas.height = source.naturalHeight;
      maskRef.current.width = source.naturalWidth;
      maskRef.current.height = source.naturalHeight;
      if (mask.complete && mask.naturalWidth) {
        maskRef.current.getContext("2d")!.drawImage(mask, 0, 0, canvas.width, canvas.height);
        render();
      }
    };
    mask.onload = () => {
      const canvas = displayRef.current;
      if (canvas?.width) {
        maskRef.current.getContext("2d")!.drawImage(mask, 0, 0, canvas.width, canvas.height);
        render();
      }
    };
    source.src = sourceUrl;
    mask.src = maskUrl;
    return () => URL.revokeObjectURL(sourceUrl);
  }, [sourceFile, maskUrl, render]);

  const snapshot = () => {
    const ctx = maskRef.current.getContext("2d")!;
    setHistory((items) => [...items.slice(-14), ctx.getImageData(0, 0, maskRef.current.width, maskRef.current.height)]);
    setFuture([]);
  };

  const paint = (event: React.PointerEvent<HTMLCanvasElement>) => {
    if (!drawing.current) return;
    const canvas = event.currentTarget;
    const bounds = canvas.getBoundingClientRect();
    const x = (event.clientX - bounds.left) * canvas.width / bounds.width;
    const y = (event.clientY - bounds.top) * canvas.height / bounds.height;
    const ctx = maskRef.current.getContext("2d")!;
    ctx.fillStyle = mode === "restore" ? "white" : "black";
    ctx.beginPath();
    ctx.arc(x, y, brush * canvas.width / bounds.width / 2, 0, Math.PI * 2);
    ctx.fill();
    render();
  };

  const undo = () => {
    const previous = history.at(-1);
    if (!previous) return;
    const ctx = maskRef.current.getContext("2d")!;
    setFuture((items) => [ctx.getImageData(0, 0, maskRef.current.width, maskRef.current.height), ...items]);
    ctx.putImageData(previous, 0, 0);
    setHistory((items) => items.slice(0, -1));
    render();
  };
  const redo = () => {
    const next = future[0];
    if (!next) return;
    const ctx = maskRef.current.getContext("2d")!;
    setHistory((items) => [...items, ctx.getImageData(0, 0, maskRef.current.width, maskRef.current.height)]);
    ctx.putImageData(next, 0, 0);
    setFuture((items) => items.slice(1));
    render();
  };
  const save = async () => {
    setSaving(true);
    try {
      const blob = await new Promise<Blob>((resolve, reject) => maskRef.current.toBlob((value) => value ? resolve(value) : reject(new Error("No se pudo crear la máscara")), "image/png"));
      onComposed(await composeMask(jobId, blob, background, color));
    } finally { setSaving(false); }
  };

  return (
    <section className="mt-6 rounded-xl border bg-card p-4">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="mr-auto font-semibold">Corregir máscara</h3>
        <Button type="button" size="sm" variant={mode === "restore" ? "brand" : "outline"} onClick={() => setMode("restore")}>
          <Paintbrush className="size-4" /> Restaurar
        </Button>
        <Button type="button" size="sm" variant={mode === "erase" ? "brand" : "outline"} onClick={() => setMode("erase")}>
          <Eraser className="size-4" /> Borrar
        </Button>
        <Button type="button" size="icon" variant="outline" onClick={undo} disabled={!history.length} aria-label="Deshacer"><RotateCcw className="size-4" /></Button>
        <Button type="button" size="icon" variant="outline" onClick={redo} disabled={!future.length} aria-label="Rehacer"><RotateCw className="size-4" /></Button>
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <label className="text-xs text-muted-foreground">Pincel: {brush}px
          <input className="mt-1 w-full accent-[var(--brand)]" type="range" min="8" max="120" value={brush} onChange={(event) => setBrush(Number(event.target.value))} />
        </label>
        <label className="text-xs text-muted-foreground">Zoom: {zoom}%
          <input className="mt-1 w-full accent-[var(--brand)]" type="range" min="50" max="200" value={zoom} onChange={(event) => setZoom(Number(event.target.value))} />
        </label>
      </div>
      <div className="checkerboard mt-3 max-h-[560px] overflow-auto rounded-lg border p-2">
        <canvas ref={displayRef} className="mx-auto touch-none cursor-crosshair" style={{ width: `${zoom}%`, maxWidth: "none" }}
          onPointerDown={(event) => { snapshot(); drawing.current = true; event.currentTarget.setPointerCapture(event.pointerId); paint(event); }}
          onPointerMove={paint} onPointerUp={() => { drawing.current = false; }} onPointerCancel={() => { drawing.current = false; }} />
      </div>
      <div className="mt-3 flex justify-end">
        <Button type="button" variant="brand" onClick={save} disabled={saving}><Save className="size-4" /> {saving ? "Aplicando…" : "Aplicar corrección"}</Button>
      </div>
    </section>
  );
}
