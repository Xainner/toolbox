import type { LucideIcon } from "lucide-react";
import {
  Combine,
  Scissors,
  FileArchive,
  RotateCw,
  FileImage,
  Images,
  Droplet,
  Lock,
  Unlock,
  Eraser,
  Repeat,
  Minimize2,
  Maximize2,
  Crop,
  Laugh,
  Grid3x3,
  ZoomIn,
  ScanText,
  PanelsTopLeft,
  Sparkles,
} from "lucide-react";

/** Opción de formulario declarada por una herramienta */
export interface ToolOption {
  name: string;
  label: string;
  type: "select" | "number" | "text" | "switch" | "range" | "color";
  default?: string | number | boolean;
  choices?: { value: string; label: string }[];
  min?: number;
  max?: number;
  step?: number;
  placeholder?: string;
  help?: string;
  visible_when?: { name: string; equals: unknown };
  advanced?: boolean;
  group?: string;
  control?: "color" | "range";
}

export type ToolCategory = "pdf" | "imagen";

/** Declaración de herramienta — espejo del registry del backend */
export interface ToolMeta {
  id: string;
  name: string;
  description: string;
  category: ToolCategory;
  multiple: boolean;
  accept: string[];
  output_hint: string;
  icon: string;
  options: ToolOption[];
  ui_mode?: "generic" | "image_compare" | "mask_editor" | "pdf_organizer";
  ai?: boolean;
}

export type JobState = "queued" | "running" | "succeeded" | "failed";

export interface Artifact {
  id: string;
  name: string;
  kind: "result" | "preview" | "mask" | "sidecar";
  mime: string;
  size: number;
  url: string;
}

export interface JobStatus {
  job_id: string;
  status: JobState;
  progress: number;
  stage: string;
  error?: string | null;
  output_name?: string;
  output_size?: number;
  input_size?: number;
  duration_ms?: number;
  download_url?: string | null;
  artifacts: Artifact[];
}

export const TOOL_ICONS: Record<string, LucideIcon> = {
  combine: Combine,
  scissors: Scissors,
  archive: FileArchive,
  rotate: RotateCw,
  fileimage: FileImage,
  images: Images,
  droplet: Droplet,
  lock: Lock,
  unlock: Unlock,
  eraser: Eraser,
  repeat: Repeat,
  minimize: Minimize2,
  maximize: Maximize2,
  crop: Crop,
  laugh: Laugh,
  grid: Grid3x3,
  zoom: ZoomIn,
  scantext: ScanText,
  panels: PanelsTopLeft,
  sparkles: Sparkles,
};

export function toolIcon(key: string): LucideIcon {
  return TOOL_ICONS[key] ?? FileArchive;
}
