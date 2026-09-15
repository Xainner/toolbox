"""Herramientas de imagen: remove-bg, convert, compress, resize."""
from __future__ import annotations

import io
from pathlib import Path
from typing import List

from PIL import Image

from tools.common import ToolError, safe_stem, filter_by_accept, single
from app.registry import ToolMeta, register
from tools.pdf_tools import make_zip

Image.MAX_IMAGE_PIXELS = 300_000_000

RASTER = [".jpg", ".jpeg", ".png", ".webp"]


def _save(img: Image.Image, dest: Path, fmt: str, quality: int = 90):
    fmt_up = fmt.upper()
    if fmt_up == "JPG":
        fmt_up = "JPEG"
    params = {}
    if fmt_up in ("JPEG", "WEBP"):
        params["quality"] = quality
        if fmt_up == "JPEG":
            img = img.convert("RGB")
    if fmt_up == "PNG" and img.mode == "P":
        img = img.convert("RGBA")
    img.save(dest, format=fmt_up, **params)


# Cache de sesiones por modelo: recargar un modelo por archivo es muy costoso
_SESSIONS: dict[str, object] = {}


def _get_session(model: str):
    from rembg import new_session
    if model not in _SESSIONS:
        _SESSIONS[model] = new_session(model)
    return _SESSIONS[model]


@register(ToolMeta(
    id="remove-bg", name="Quitar fondo (IA)", category="imagen",
    description="Recorte local de alta calidad con presets, bordes refinados y máscara editable.",
    multiple=True, accept=RASTER, output_hint="PNG con fondo transparente", icon="eraser",
    ui_mode="mask_editor", ai=True,
    options=[
        {"name": "preset", "label": "Calidad", "type": "select",
         "choices": [
             {"value": "fast", "label": "Rápido · U2NetP"},
             {"value": "balanced", "label": "Equilibrado · ISNet"},
             {"value": "quality", "label": "Alta calidad · BiRefNet General"},
             {"value": "portrait", "label": "Retratos · BiRefNet Portrait"},
         ],
         "default": "quality",
         "help": "Los modelos grandes descargan una sola vez y quedan en el servidor"},
        {"name": "edge_mode", "label": "Tratamiento de bordes", "type": "select", "default": "decontaminate",
         "choices": [
             {"value": "none", "label": "Ninguno · bordes duros"},
             {"value": "decontaminate", "label": "Descontaminar color · recomendado"},
             {"value": "alpha", "label": "Alpha matting · cabello"},
             {"value": "vitmatte", "label": "ViTMatte · máximo detalle"},
         ], "group": "advanced", "advanced": True},
        {"name": "erode", "label": "Erosión de borde (px)", "type": "number", "default": 8,
         "min": 0, "max": 40, "help": "Solo con alpha matting",
         "visible_when": {"name": "edge_mode", "equals": "alpha"}, "advanced": True},
        {"name": "binary_mask", "label": "Máscara binaria", "type": "switch", "default": False,
         "help": "Úsala solo para logos y objetos de borde completamente duro", "advanced": True},
        {"name": "post", "label": "Fondo resultante", "type": "select",
         "choices": [
             {"value": "transparent", "label": "Transparente"},
             {"value": "white", "label": "Blanco sólido"},
             {"value": "color", "label": "Color personalizado"},
         ],
         "default": "transparent"},
        {"name": "color", "label": "Color (hex)", "type": "text", "default": "#ffffff",
         "placeholder": "#rrggbb", "help": "Solo si eliges color personalizado",
         "control": "color", "visible_when": {"name": "post", "equals": "color"}},
    ],
))
def remove_bg(files: List[Path], options: dict, workdir: Path) -> List[Path]:
    files = filter_by_accept(files, RASTER)
    post = options.get("post", "transparent")
    preset = str(options.get("preset") or "quality")
    model = {"fast": "u2netp", "balanced": "isnet-general-use",
             "quality": "birefnet-general", "portrait": "birefnet-portrait"}.get(preset, "birefnet-general")

    try:
        from rembg import remove
    except ImportError:
        raise ToolError("Motor de IA no disponible en este despliegue")

    session = _get_session(model)

    edge_mode = str(options.get("edge_mode") or "decontaminate")
    alpha_matting = edge_mode == "alpha"
    erode = int(options.get("erode") or 0)
    kwargs = {
        "session": session,
        "post_process_mask": bool(options.get("binary_mask", False)),
    }
    if alpha_matting:
        try:
            import pymatting  # noqa: F401
        except ImportError:
            raise ToolError("Alpha matting no está disponible en este despliegue")
        kwargs["alpha_matting"] = True
        kwargs["alpha_matting_foreground_threshold"] = 240
        kwargs["alpha_matting_background_threshold"] = 15
        kwargs["alpha_matting_erodesize"] = max(1, erode)

    outs = []
    for src in files:
        inp = Image.open(src).convert("RGBA")
        if len(files) == 1:
            inp.save(workdir / "_source.png")
        buf_in = io.BytesIO()
        inp.save(buf_in, format="PNG")
        result = remove(buf_in.getvalue(), **kwargs)
        out_img = Image.open(io.BytesIO(result)).convert("RGBA")
        if edge_mode == "decontaminate":
            out_img = _decontaminate(inp, out_img)
        elif edge_mode == "vitmatte":
            out_img = _vitmatte(inp, out_img)

        if len(files) == 1:
            out_img.getchannel("A").save(workdir / "mascara.png")

        if post != "transparent":
            bg = Image.new("RGB", out_img.size)
            hexcolor = str(options.get("color") or "#ffffff").strip()
            try:
                rgb = tuple(int(hexcolor.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
            except Exception:
                rgb = (255, 255, 255)
            bg.putdata([rgb for _ in range(out_img.width * out_img.height)])
            # composite correcto: pegar imagen sobre fondo usando su propio alpha
            bg.paste(out_img, (0, 0), out_img)
            final_path = workdir / f"{safe_stem(src.name)}_sin_fondo.png"
            bg.save(final_path, format="PNG")
        else:
            final_path = workdir / f"{safe_stem(src.name)}_sin_fondo.png"
            out_img.save(final_path, format="PNG")
        outs.append(final_path)

    if len(outs) == 1:
        return outs
    return [make_zip(outs, workdir / "imagenes-sin-fondo.zip")]


def _decontaminate(source: Image.Image, cutout: Image.Image) -> Image.Image:
    """Reduce halos estimando el color del fondo alrededor de los píxeles semitransparentes."""
    import numpy as np
    src = np.asarray(source.convert("RGB"), dtype=np.float32)
    out = np.asarray(cutout.convert("RGBA"), dtype=np.float32).copy()
    alpha = out[..., 3:4] / 255.0
    bg_weight = 1.0 - alpha
    from PIL import ImageFilter
    weighted = Image.fromarray(np.uint8(src * bg_weight)).filter(ImageFilter.GaussianBlur(6))
    weights = Image.fromarray(np.uint8(bg_weight[..., 0] * 255)).filter(ImageFilter.GaussianBlur(6))
    bg = np.asarray(weighted, dtype=np.float32) / np.maximum(np.asarray(weights, dtype=np.float32)[..., None] / 255.0, 0.04)
    edge = (alpha > 0.02) & (alpha < 0.98)
    clean = (src - bg * (1.0 - alpha)) / np.maximum(alpha, 0.04)
    out[..., :3] = np.where(edge, np.clip(clean, 0, 255), out[..., :3])
    return Image.fromarray(np.uint8(np.clip(out, 0, 255)), "RGBA")


def _vitmatte(source: Image.Image, cutout: Image.Image) -> Image.Image:
    """Refina la máscara con el checkpoint local de ViTMatte; descarga una vez al volumen de modelos."""
    try:
        import numpy as np
        import torch
        from transformers import VitMatteImageProcessor, VitMatteForImageMatting
    except ImportError as exc:
        raise ToolError("ViTMatte requiere el perfil de IA completo") from exc
    model_id = "hustvl/vitmatte-small-composition-1k"
    device = "cuda" if torch.cuda.is_available() else "cpu"
    processor = VitMatteImageProcessor.from_pretrained(model_id)
    model = VitMatteForImageMatting.from_pretrained(model_id).to(device).eval()
    alpha = np.asarray(cutout.getchannel("A"), dtype=np.uint8)
    trimap = np.where(alpha > 245, 255, np.where(alpha < 10, 0, 128)).astype(np.uint8)
    inputs = processor(images=source.convert("RGB"), trimaps=Image.fromarray(trimap), return_tensors="pt")
    with torch.no_grad():
        prediction = model(**{k: v.to(device) for k, v in inputs.items()}).alphas
    refined = torch.nn.functional.interpolate(prediction, size=(source.height, source.width), mode="bilinear", align_corners=False)
    refined_alpha = Image.fromarray(np.uint8(refined[0, 0].clamp(0, 1).cpu().numpy() * 255))
    result = source.copy()
    result.putalpha(refined_alpha)
    return result


@register(ToolMeta(
    id="convert-image", name="Convertir imagen", category="imagen",
    description="Convierte entre JPG, PNG y WEBP.",
    multiple=True, accept=RASTER,
    output_hint="imagen(s) en el formato elegido", icon="repeat",
    options=[
        {"name": "format", "label": "Formato destino", "type": "select",
         "choices": [
             {"value": "png", "label": "PNG"},
             {"value": "jpg", "label": "JPG"},
             {"value": "webp", "label": "WEBP"},
         ],
         "default": "png"},
        {"name": "quality", "label": "Calidad", "type": "number", "default": 90, "min": 10, "max": 100},
    ],
))
def convert_image(files: List[Path], options: dict, workdir: Path) -> List[Path]:
    files = filter_by_accept(files, RASTER)
    fmt = str(options.get("format", "png")).lower().lstrip(".")
    if fmt not in ("png", "jpg", "webp"):
        raise ToolError("Formato no soportado")
    quality = int(options.get("quality", 90))

    outs = []
    for src in files:
        img = Image.open(src)
        ext = ".jpg" if fmt == "jpg" else f".{fmt}"
        out = workdir / f"{safe_stem(src.name)}{ext}"
        _save(img, out, fmt, quality)
        outs.append(out)

    if len(outs) == 1:
        return outs
    return [make_zip(outs, workdir / "imagenes-convertidas.zip")]


@register(ToolMeta(
    id="compress-image", name="Comprimir imagen", category="imagen",
    description="Reduce el peso de tus imágenes ajustando calidad y reescalado opcional.",
    multiple=True, accept=RASTER, output_hint="imagen(s) más liviana(s)", icon="minimize",
    options=[
        {"name": "quality", "label": "Calidad", "type": "number", "default": 70, "min": 10, "max": 95},
        {"name": "scale", "label": "Reescalar a %", "type": "number", "default": 100, "min": 5, "max": 100},
    ],
))
def compress_image(files: List[Path], options: dict, workdir: Path) -> List[Path]:
    files = filter_by_accept(files, RASTER)
    quality = int(options.get("quality", 70))
    scale = int(options.get("scale", 100)) / 100.0

    outs = []
    for src in files:
        img = Image.open(src)
        if scale < 1.0:
            w = max(1, int(img.width * scale))
            h = max(1, int(img.height * scale))
            img = img.resize((w, h), Image.LANCZOS)

        # Elegir formato de salida: mantiene el original salvo PNG→JPG para ganar compresión
        src_ext = src.suffix.lower()
        if src_ext == ".png":
            has_alpha = img.mode in ("RGBA", "LA", "PA")
            if not has_alpha:
                dest_fmt, ext = "jpg", ".jpg"
            else:
                dest_fmt, ext = "png", ".png"
        elif src_ext == ".webp":
            dest_fmt, ext = "webp", ".webp"
        else:
            dest_fmt, ext = "jpg", ".jpg"

        out = workdir / f"{safe_stem(src.name)}_comprimida{ext}"
        _save(img, out, dest_fmt, quality)
        outs.append(out)

    if len(outs) == 1:
        return outs
    return [make_zip(outs, workdir / "imagenes-comprimidas.zip")]


@register(ToolMeta(
    id="resize-image", name="Redimensionar imagen", category="imagen",
    description="Cambia el tamaño por píxeles o porcentaje, manteniendo proporción.",
    multiple=True, accept=RASTER, output_hint="imagen(s) redimensionada(s)", icon="maximize",
    options=[
        {"name": "mode", "label": "Modo", "type": "select",
         "choices": [{"value": "percent", "label": "Porcentaje"}, {"value": "pixels", "label": "Píxeles"}],
         "default": "percent"},
        {"name": "width", "label": "Ancho (%) o px", "type": "number", "default": 50, "min": 1},
        {"name": "height", "label": "Alto (%) o px", "type": "number", "default": 50, "min": 1},
        {"name": "keep_ratio", "label": "Mantener proporción", "type": "switch", "default": True,
         "help": "usa solo el ancho como referencia"},
    ],
))
def resize_image(files: List[Path], options: dict, workdir: Path) -> List[Path]:
    files = filter_by_accept(files, RASTER)
    mode = options.get("mode", "percent")
    width = options.get("width")
    height = options.get("height")
    keep_ratio = bool(options.get("keep_ratio", True))

    outs = []
    for src in files:
        img = Image.open(src)
        w0, h0 = img.size

        if mode == "percent":
            wp = float(width or 100) / 100.0
            hp = float(height or 100) / 100.0
            if keep_ratio:
                hp = wp
            nw, nh = max(1, round(w0 * wp)), max(1, round(h0 * hp))
        else:
            tw = int(width) if width else None
            th = int(height) if height else None
            if keep_ratio:
                if tw:
                    th = None
                    ratio = tw / w0
                    nw, nh = tw, max(1, round(h0 * ratio))
                elif th:
                    ratio = th / h0
                    nw, nh = max(1, round(w0 * ratio)), th
                else:
                    raise ToolError("Indica ancho o alto en píxeles")
            else:
                if not tw or not th:
                    raise ToolError("Con proporción libre indica ancho Y alto")
                nw, nh = tw, th

        img = img.resize((nw, nh), Image.LANCZOS)
        ext = src.suffix.lower()
        if ext not in (".jpg", ".jpeg", ".png", ".webp"):
            ext = ".png"
        out = workdir / f"{safe_stem(src.name)}_{nw}x{nh}{ext}"
        _save(img, out, ext.lstrip("."), 92)
        outs.append(out)

    if len(outs) == 1:
        return outs
    return [make_zip(outs, workdir / "imagenes-redimensionadas.zip")]
