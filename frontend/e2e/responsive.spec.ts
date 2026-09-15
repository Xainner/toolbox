import { expect, test } from "@playwright/test";

const tools = [{
  id: "remove-bg", name: "Quitar fondo (IA)", category: "imagen", description: "Recorte local",
  multiple: true, accept: [".png"], output_hint: "PNG", icon: "eraser", ui_mode: "mask_editor", ai: true,
  options: [
    { name: "preset", label: "Calidad", type: "select", default: "quality", choices: [{ value: "quality", label: "Alta calidad" }] },
    { name: "post", label: "Fondo", type: "select", default: "transparent", choices: [{ value: "transparent", label: "Transparente" }, { value: "color", label: "Color" }] },
    { name: "color", label: "Color", type: "text", default: "#ffffff", control: "color", visible_when: { name: "post", equals: "color" } },
  ],
}];

test.beforeEach(async ({ page }) => {
  await page.route("**/api/tools", (route) => route.fulfill({ json: { tools } }));
  await page.route("**/api/stats", (route) => route.fulfill({ json: { jobs: [] } }));
});

test("búsqueda y actividad siguen disponibles en móvil", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Buscar herramientas" })).toBeVisible();
  await expect(page.getByLabel("Actividad")).toBeVisible();
  await expect(page.locator("body")).not.toHaveCSS("overflow-x", "scroll");
});

test("una recarga directa conserva defaults y condiciones", async ({ page }) => {
  await page.goto("/tool/remove-bg");
  await expect(page.getByLabel("Calidad")).toContainText("Alta calidad");
  await expect(page.getByLabel("Color hexadecimal")).toHaveCount(0);
  await page.getByLabel("Fondo").click();
  await page.getByRole("option", { name: "Color" }).click();
  await expect(page.getByLabel("Color hexadecimal")).toBeVisible();
});
