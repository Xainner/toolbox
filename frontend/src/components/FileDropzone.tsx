import { useCallback, useEffect, useState } from "react";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import { restrictToVerticalAxis, restrictToParentElement } from "@dnd-kit/modifiers";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable,
  arrayMove,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical, X, FileText, Image as ImageIcon, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

export interface DropzoneFile {
  id: string;
  file: File;
}

export function formatBytes(n: number): string {
  if (!n) return "0 B";
  const k = 1024;
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.min(Math.floor(Math.log(n) / Math.log(k)), units.length - 1);
  return `${(n / Math.pow(k, i)).toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

interface FileRowProps {
  item: DropzoneFile;
  onRemove: (id: string) => void;
  disabled?: boolean;
  index: number;
}

function FileRow({ item, onRemove, disabled, index }: FileRowProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: item.id,
    disabled,
  });

  const isPdf = item.file.name.toLowerCase().endsWith(".pdf");
  const Icon = isPdf ? FileText : ImageIcon;
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <li
      ref={setNodeRef}
      style={style}
      className={cn(
        "flex items-center gap-3 rounded-lg border bg-card px-3 py-2.5",
        isDragging && "relative z-10 opacity-90 shadow-xl ring-2 ring-brand/40",
        disabled && "opacity-60"
      )}
    >
      <button
        type="button"
        className="cursor-grab touch-none rounded p-0.5 text-muted-foreground hover:bg-accent hover:text-foreground active:cursor-grabbing"
        aria-label="Arrastrar para reordenar"
        {...attributes}
        {...listeners}
        disabled={disabled}
      >
        <GripVertical className="size-4" />
        <span className="sr-only">Arrastrar</span>
      </button>
      <span className="grid size-7 shrink-0 place-items-center rounded bg-brand/10 text-brand">
        <Icon className="size-4" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{item.file.name}</p>
      </div>
      <span className="shrink-0 font-mono text-xs text-muted-foreground">#{index + 1}</span>
      <span className="hidden shrink-0 text-xs text-muted-foreground sm:inline">{formatBytes(item.file.size)}</span>
      <Button
        variant="ghost"
        size="icon"
        className="size-7 text-muted-foreground hover:text-destructive"
        onClick={() => onRemove(item.id)}
        disabled={disabled}
        aria-label={`Quitar ${item.file.name}`}
      >
        <X className="size-4" />
      </Button>
    </li>
  );
}

interface DropzoneProps {
  files: DropzoneFile[];
  onChange: (files: DropzoneFile[]) => void;
  accept: string[];
  multiple: boolean;
  disabled?: boolean;
  /** Registra una función para abrir el selector de archivos desde fuera */
  registerPicker?: (open: () => void) => void;
}

/**
 * Zona de carga con drag & drop nativo (soltar archivos del SO)
 * y reordenamiento con dnd-kit cuando la herramienta acepta varios.
 */
export default function FileDropzone({ files, onChange, accept, multiple, disabled, registerPicker }: DropzoneProps) {
  const [dragOver, setDragOver] = useState(false);
  const inputId = `dz-input-${accept.join("-").replace(/\W/g, "")}-${multiple ? "m" : "s"}`;

  const openPicker = useCallback(() => {
    const el = document.getElementById(inputId) as HTMLInputElement | null;
    el?.click();
  }, [inputId]);

  useEffect(() => {
    registerPicker?.(openPicker);
  }, [registerPicker, openPicker]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  const addFiles = useCallback(
    (incoming: FileList | File[]) => {
      const accepted = Array.from(incoming).filter((f) => {
        const ext = "." + f.name.split(".").pop()?.toLowerCase();
        return accept.includes(ext);
      });
      const next = [...files];
      for (const f of accepted) {
        if (!multiple && next.length >= 1) break;
        next.push({ id: `${f.name}-${f.size}-${Math.random().toString(36).slice(2, 8)}`, file: f });
      }
      if (accepted.length > 0) onChange(next);
    },
    [files, accept, multiple, onChange]
  );

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (disabled) return;
    if (e.dataTransfer.files?.length) addFiles(e.dataTransfer.files);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      const oldIndex = files.findIndex((f) => f.id === active.id);
      const newIndex = files.findIndex((f) => f.id === over.id);
      onChange(arrayMove(files, oldIndex, newIndex));
    }
  };

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      className={cn(
        "rounded-xl border-2 border-dashed p-6 transition-colors",
        dragOver ? "border-brand bg-brand/5" : "border-border hover:border-brand/50"
      )}
    >
      {files.length === 0 ? (
        <label
          htmlFor={inputId}
          className="flex cursor-pointer flex-col items-center justify-center gap-2 py-10 text-center select-none"
        >
          <span className="grid size-14 place-items-center rounded-full bg-brand/10 text-brand">
            <ImageIcon className="size-6" />
          </span>
          <span className="font-medium">
            Selecciona archivos o arrástralos aquí
          </span>
          <span className="text-xs text-muted-foreground">
            Formatos: {accept.join(", ")} {multiple ? "· puedes agregar varios" : "· un archivo"}
          </span>
          {multiple && (
            <span className="mt-1 text-xs text-muted-foreground/70">
              Después podrás reordenarlos arrastrándolos
            </span>
          )}
        </label>
      ) : null}

      {files.length > 0 && (
        <>
          {multiple && (
            <p className="mb-3 flex items-center gap-2 text-xs text-muted-foreground">
              <Loader2 className="hidden size-3 animate-spin" />
              Arrastra las filas para cambiar el orden — el resultado respeta el orden que dejes aquí.
            </p>
            )}
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            modifiers={[restrictToVerticalAxis, restrictToParentElement]}
            onDragEnd={handleDragEnd}
          >
            <SortableContext items={files.map((f) => f.id)} strategy={verticalListSortingStrategy}>
              <ul className="flex flex-col gap-2">
                {files.map((f, idx) => (
                  <FileRow key={f.id} item={f} index={idx} onRemove={(id) => onChange(files.filter((x) => x.id !== id))} disabled={disabled} />
                ))}
              </ul>
            </SortableContext>
          </DndContext>
          {!disabled && (
            <div className="mt-4 flex items-center gap-3">
              <label htmlFor={inputId}>
                <Button type="button" variant="outline" size="sm" asChild>
                  <span>{multiple ? "+ Agregar más" : "Cambiar archivo"}</span>
                </Button>
              </label>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => onChange([])}
              >
                Quitar todos
                </Button>
            </div>
          )}
        </>
      )}

      <input
        id={inputId}
        type="file"
        className="sr-only"
        accept={accept.join(",")}
        multiple={multiple}
        disabled={disabled}
        onChange={(e) => {
          if (e.target.files) addFiles(e.target.files);
          e.target.value = "";
        }}
      />
    </div>
  );
}
