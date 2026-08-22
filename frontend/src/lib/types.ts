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
} from "lucide-react";

/** Opción de formulario declarada por una herramienta */
export interface ToolOption {
  name: string;
  label: string;
  type: "select" | "number" | "text" | "switch";
  default?: string | number | boolean;
  choices?: { value: string; label: string }[];
  min?: number;
  max?: number;
  step?: number;
  placeholder?: string;
  help?: string;
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
};

export function toolIcon(key: string): LucideIcon {
  return TOOL_ICONS[key] ?? FileArchive;
}
