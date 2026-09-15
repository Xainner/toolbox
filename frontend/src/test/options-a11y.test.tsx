import { describe, expect, it, vi } from "vitest";
import { render } from "@testing-library/react";
import { axe } from "jest-axe";
import { OptionFields } from "@/pages/ToolPage";

describe("accesibilidad de opciones", () => {
  it("no introduce violaciones automáticas", async () => {
    const { container } = render(<OptionFields
      options={[{ name: "quality", label: "Calidad", type: "number", min: 1, max: 100, help: "Porcentaje" },
        { name: "enabled", label: "Activar mejora", type: "switch", default: true }]}
      values={{ quality: 80, enabled: true }} onChange={vi.fn()} disabled={false} errors={{}} />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
