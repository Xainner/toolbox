import { useEffect, useState } from "react";
import { DndContext, PointerSensor, KeyboardSensor, closestCenter, useSensor, useSensors, type DragEndEvent } from "@dnd-kit/core";
import { SortableContext, arrayMove, rectSortingStrategy, sortableKeyboardCoordinates, useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Grip, RotateCw, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";

export interface PageOperation { index: number; rotation: number }
interface PageItem extends PageOperation { id: string; thumbnail: string }

function SortablePage({ page, number, onRotate, onDelete }: {
  page: PageItem; number: number; onRotate: () => void; onDelete: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: page.id });
  return (
    <article ref={setNodeRef} style={{ transform: CSS.Transform.toString(transform), transition }}
      className={`rounded-xl border bg-card p-2 ${isDragging ? "z-10 opacity-70 ring-2 ring-brand" : ""}`}>
      <div className="checkerboard relative aspect-[3/4] overflow-hidden rounded-lg bg-muted">
        <img src={page.thumbnail} alt={`Página ${page.index + 1}`} className="size-full object-contain"
          style={{ transform: `rotate(${page.rotation}deg)` }} />
        <button type="button" {...attributes} {...listeners} aria-label={`Mover página ${number}`}
          className="absolute left-1 top-1 cursor-grab rounded-md bg-black/70 p-1.5 text-white active:cursor-grabbing">
          <Grip className="size-4" />
        </button>
      </div>
      <div className="mt-2 flex items-center justify-between gap-1">
        <span className="pl-1 text-xs font-medium">Página {number}</span>
        <div className="flex">
          <Button type="button" variant="ghost" size="icon" className="size-8" onClick={onRotate} aria-label={`Rotar página ${number}`}>
            <RotateCw className="size-4" />
          </Button>
          <Button type="button" variant="ghost" size="icon" className="size-8 hover:text-destructive" onClick={onDelete}
            aria-label={`Eliminar página ${number}`}><Trash2 className="size-4" /></Button>
        </div>
      </div>
    </article>
  );
}

export default function PdfOrganizer({ file, onChange }: { file: File; onChange: (pages: PageOperation[]) => void }) {
  const [pages, setPages] = useState<PageItem[]>([]);
  const [loading, setLoading] = useState(true);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }));

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    (async () => {
      const pdfjs = await import("pdfjs-dist");
      const worker = await import("pdfjs-dist/build/pdf.worker.min.mjs?url");
      pdfjs.GlobalWorkerOptions.workerSrc = worker.default;
      const document = await pdfjs.getDocument({ data: await file.arrayBuffer() }).promise;
      const loaded: PageItem[] = [];
      for (let index = 0; index < document.numPages; index += 1) {
        const page = await document.getPage(index + 1);
        const base = page.getViewport({ scale: 1 });
        const viewport = page.getViewport({ scale: Math.min(0.45, 210 / base.width) });
        const canvas = window.document.createElement("canvas");
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        await page.render({ canvas, canvasContext: canvas.getContext("2d")!, viewport }).promise;
        loaded.push({ id: `page-${index}`, index, rotation: 0, thumbnail: canvas.toDataURL("image/jpeg", 0.78) });
      }
      if (!cancelled) { setPages(loaded); setLoading(false); }
    })().catch(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [file]);

  useEffect(() => { if (pages.length) onChange(pages.map(({ index, rotation }) => ({ index, rotation }))); }, [pages, onChange]);

  const dragEnd = ({ active, over }: DragEndEvent) => {
    if (!over || active.id === over.id) return;
    setPages((current) => arrayMove(current, current.findIndex((p) => p.id === active.id), current.findIndex((p) => p.id === over.id)));
  };

  if (loading) return <div className="rounded-xl border p-8 text-center text-sm text-muted-foreground">Generando miniaturas…</div>;
  if (!pages.length) return <div className="rounded-xl border p-8 text-center text-sm text-destructive">No se pudieron leer las páginas.</div>;
  return (
    <div className="mt-4">
      <p className="mb-3 text-xs text-muted-foreground">Arrastra para ordenar. Puedes rotar o eliminar páginas antes de ejecutar.</p>
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={dragEnd}>
        <SortableContext items={pages.map((page) => page.id)} strategy={rectSortingStrategy}>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
            {pages.map((page, index) => <SortablePage key={page.id} page={page} number={index + 1}
              onRotate={() => setPages((current) => current.map((item) => item.id === page.id ? { ...item, rotation: (item.rotation + 90) % 360 } : item))}
              onDelete={() => setPages((current) => current.length > 1 ? current.filter((item) => item.id !== page.id) : current)} />)}
          </div>
        </SortableContext>
      </DndContext>
    </div>
  );
}
