"""Generador de mockups de producto: compone un dise\u00f1o sobre un template."""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

from PIL import Image

from app.registry import ToolMeta, register
from tools.common import ToolError, safe_stem, single

Image.MAX_IMAGE_PIXELS = 300_000_000

RASTER = [".png", ".jpg", ".jpeg", ".webp"]

ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets" / "mockups"
CONFIG_PATH = ASSETS_DIR / "mockup_templates.json"


def _load_templates():
    if not CONFIG_PATH.exists():
        raise ToolError("No existe la configuraci\u00f3n de templates de mockup")
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ToolError("Configuraci\u00f3n de templates inv\u00e1lida") from exc
    if not isinstance(data, dict) or not data:
        raise ToolError("Configuraci\u00f3n de templates inv\u00e1lida")
    return data


def _trim_transparency(img: Image.Image) -> Image.Image:
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    bbox = img.getbbox()
    if not bbox:
        raise ToolError("El dise\u00f1o no contiene p\u00edxeles visibles")
    return img.crop(bbox)


def _hex_to_rgb(value: str):
    value = (value or "#ffffff").strip().lstrip("#")
    if len(value) != 6:
        return (255, 255, 255)
    try:
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return (255, 255, 255)


def _apply_opacity(img: Image.Image, opacity_percent: int) -> Image.Image:
    opacity_percent = max(1, min(100, int(opacity_percent)))
    if opacity_percent == 100:
        return img
    img = img.copy().convert("RGBA")
    alpha = img.getchannel("A")
    factor = opacity_percent / 100.0
    alpha = alpha.point(lambda p: int(p * factor))
    img.putalpha(alpha)
    return img


def _parse_print_box(conf: dict):
    box = conf.get("print_box")
    if not isinstance(box, (list, tuple)) or len(box) != 4:
        raise ToolError("Template mal configurado: print_box inv\u00e1lido")
    try:
        x1, y1, x2, y2 = (int(v) for v in box)
    except Exception as exc:
        raise ToolError("Template mal configurado: print_box inv\u00e1lido") from exc
    if x2 <= x1 or y2 <= y1:
        raise ToolError("Template mal configurado: print_box inv\u00e1lido")
    return x1, y1, x2, y2


@register(ToolMeta(
    id="product-mockup",
    name="Generador de Mockup",
    category="imagen",
    description="Coloca un dise\u00f1o dentro de una plantilla de producto y genera un mockup final.",
    multiple=False,
    accept=RASTER,
    output_hint="mockup final listo para descargar",
    icon="shirt",
    options=[
        {
            "name": "template",
            "label": "Template base",
            "type": "select",
            "choices": [
                {"value": "black-shirt-v1", "label": "Camisa negra sola"},
                {"value": "female-black-shirt-v1", "label": "Modelo femenina con camisa negra"},
            ],
            "default": "black-shirt-v1",
        },
        {"name": "scale", "label": "Escala del dise\u00f1o (%)", "type": "number", "default": 90, "min": 10, "max": 150},
        {"name": "offset_x", "label": "Mover horizontal (px)", "type": "number", "default": 0, "min": -300, "max": 300},
        {"name": "offset_y", "label": "Mover vertical (px)", "type": "number", "default": 0, "min": -300, "max": 300},
        {"name": "opacity", "label": "Opacidad del dise\u00f1o (%)", "type": "number", "default": 100, "min": 1, "max": 100},
        {
            "name": "format",
            "label": "Formato de salida",
            "type": "select",
            "choices": [{"value": "png", "label": "PNG"}, {"value": "jpg", "label": "JPG"}],
            "default": "png",
        },
        {"name": "bgcolor", "label": "Color de fondo JPG", "type": "text", "default": "#ffffff", "placeholder": "#rrggbb"},
    ],
))
def product_mockup(files: List[Path], options: dict, workdir: Path) -> List[Path]:
    src = single(files, "product-mockup")
    templates = _load_templates()

    template_id = str(options.get("template") or "black-shirt-v1")
    if template_id not in templates:
        raise ToolError("Template no v\u00e1lido")

    conf = templates[template_id]
    template_path = ASSETS_DIR / conf.get("image", "")
    if not template_path.exists():
        raise ToolError("No existe la imagen del template seleccionado")

    x1, y1, x2, y2 = _parse_print_box(conf)
    box_w = x2 - x1
    box_h = y2 - y1

    try:
        scale = max(10, min(150, int(options.get("scale", 90)))) / 100.0
    except Exception:
        raise ToolError("Escala inv\u00e1lida")
    try:
        offset_x = int(options.get("offset_x", 0))
        offset_y = int(options.get("offset_y", 0))
        opacity = int(options.get("opacity", 100))
    except Exception:
        raise ToolError("Offset u opacidad inv\u00e1lidos")
    fmt = str(options.get("format", "png")).lower()
    if fmt not in ("png", "jpg"):
        raise ToolError("Formato de salida no soportado")

    try:
        base = Image.open(template_path).convert("RGBA")
        design = Image.open(src).convert("RGBA")
    except Exception as exc:
        raise ToolError(f"No se pudo leer una imagen: {exc}") from exc
    design = _trim_transparency(design)
    design = _apply_opacity(design, opacity)

    max_w = max(1, int(box_w * scale))
    max_h = max(1, int(box_h * scale))
    design.thumbnail((max_w, max_h), Image.LANCZOS)

    px = x1 + (box_w - design.width) // 2 + offset_x
    py = y1 + (box_h - design.height) // 2 + offset_y

    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    layer.paste(design, (px, py), design)
    out = Image.alpha_composite(base, layer)

    out_name = f"{safe_stem(src.name)}_{template_id}_mockup"
    if fmt == "png":
        final_path = workdir / f"{out_name}.png"
        out.save(final_path, format="PNG")
    else:
        rgb = Image.new("RGB", out.size, _hex_to_rgb(str(options.get("bgcolor", "#ffffff"))))
        rgb.paste(out, mask=out.getchannel("A"))
        final_path = workdir / f"{out_name}.jpg"
        rgb.save(final_path, format="JPEG", quality=95)
    return [final_path]
