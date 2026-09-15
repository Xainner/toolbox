import { describe, expect, it } from "vitest";
import { defaultValues, isVisible } from "@/pages/ToolPage";
import type { ToolMeta, ToolOption } from "@/lib/types";

const tool: ToolMeta = {
  id: "remove-bg", name: "Quitar fondo", category: "imagen", description: "", multiple: true,
  accept: [".png"], output_hint: "PNG", icon: "eraser",
  options: [
    { name: "quality", label: "Calidad", type: "select", default: "high", choices: [{ value: "high", label: "Alta" }] },
    { name: "matting", label: "Matting", type: "switch", default: true },
    { name: "erode", label: "Erosión", type: "number", default: 8 },
  ],
};

describe("formularios generados por metadata", () => {
  it("conserva defaults al cargar una ruta directa", () => {
    expect(defaultValues(tool)).toEqual({ quality: "high", matting: true, erode: 8 });
  });

  it("evalúa campos condicionales", () => {
    const option: ToolOption = { name: "color", label: "Color", type: "color", visible_when: { name: "background", equals: "color" } };
    expect(isVisible(option, { background: "transparent" })).toBe(false);
    expect(isVisible(option, { background: "color" })).toBe(true);
  });
});
