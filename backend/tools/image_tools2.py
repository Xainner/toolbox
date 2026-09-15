"""Herramientas de imagen v2 (estilo iLoveIMG): recortar, girar, marca de agua,
convertir a JPG, meme, pixelar caras y ampliar."""
from __future__ import annotations

import io
from pathlib import Path
from typing import List

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from tools.common import ToolError, safe_stem, filter_by_accept, single
from app.registry import ToolMeta, register
from tools.pdf_tools import make_zip

Image.MAX_IMAGE_PIXELS = 300_000_000

COMMON = [".jpg", ".jpeg", ".png", ".webp"]
WIDE = [".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"]
CONVERTIBLE = [".png", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".heic", ".heif"]


def _load_font(size: int):
    """Busca una fuente bold disponible en el sistema."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # contenedor
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _hex_rgb(hexcolor: str, fallback=(255, 255, 255)):
    try:
        h = hexcolor.strip().lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return fallback


def _save_out(img: Image.Image, src: Path, workdir: Path, suffix: str) -> Path:
    ext = src.suffix.lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        ext = ".png"
    out = workdir / f"{safe_stem(src.name)}{suffix}{ext}"
    params = {}
    if ext in (".jpg", ".jpeg"):
        img = img.convert("RGB")
        params["quality"] = 92
    img.save(out, **params)
    return out


# ---------------------------------------------------------------- recortar
@register(ToolMeta(
    id="crop-image", name="Recortar imagen", category="imagen",
    description="Recorta definiendo un rectángulo en píxeles.",
    multiple=True, accept=COMMON, output_hint="imagen(s) recortada(s)", icon="crop",
    options=[
        {"name": "left", "label": "X inicial (px)", "type": "number", "default": 0, "min": 0},
        {"name": "top", "label": "Y inicial (px)", "type": "number", "default": 0, "min": 0},
        {"name": "width", "label": "Ancho (px)", "type": "number", "placeholder": "vacío = hasta el borde"},
        {"name": "height", "label": "Alto (px)", "type": "number", "placeholder": "vacío = hasta el borde"},
    ],
))
def crop_image(files: List[Path], options: dict, workdir: Path) -> List[Path]:
    files = filter_by_accept(files, COMMON)
    left = int(options.get("left") or 0)
    top = int(options.get("top") or 0)
    width = options.get("width")
    height = options.get("height")

    outs = []
    for src in files:
        img = Image.open(src)
        w0, h0 = img.size
        right = min(int(width), w0 - left) if width else w0 - left
        bottom = min(int(height), h0 - top) if height else h0 - top
        if left < 0 or top < 0 or right <= 0 or bottom <= 0 or left >= w0 or top >= h0:
            raise ToolError(f"Rectángulo inválido para '{src.name}' ({w0}x{h0})")
        outs.append(_save_out(img.crop((left, top, left + right, top + bottom)), src, workdir, "_recortada"))

    if len(outs) == 1:
        return outs
    return [make_zip(outs, workdir / "imagenes-recortadas.zip")]


# ---------------------------------------------------------------- girar
@register(ToolMeta(
    id="rotate-image", name="Girar imagen", category="imagen",
    description="Rota o voltea imágenes en lote: 90°, 180°, 270° o espejo.",
    multiple=True, accept=WIDE, output_hint="imagen(es) rotada(s)", icon="rotate",
    options=[
        {"name": "angle", "label": "Rotación", "type": "select",
         "choices": [
             {"value": "0", "label": "Sin rotación"},
             {"value": "90", "label": "90° derecha"},
             {"value": "180", "label": "180°"},
             {"value": "270", "label": "90° izquierda"},
         ], "default": "90"},
        {"name": "flip", "label": "Voltear", "type": "select",
         "choices": [
             {"value": "none", "label": "No voltear"},
             {"value": "h", "label": "Horizontal (espejo)"},
             {"value": "v", "label": "Vertical"},
         ], "default": "none"},
    ],
))
def rotate_image(files: List[Path], options: dict, workdir: Path) -> List[Path]:
    files = filter_by_accept(files, WIDE)
    angle = int(options.get("angle") or 0)
    flip = str(options.get("flip") or "none")
    if angle == 0 and flip == "none":
        raise ToolError("Elige una rotación o un volteo")

    outs = []
    for src in files:
        img = Image.open(src)
        if angle == 90:
            img = img.transpose(Image.Transpose.ROTATE_270)  # visual: derecha
        elif angle == 180:
            img = img.transpose(Image.Transpose.ROTATE_180)
        elif angle == 270:
            img = img.transpose(Image.Transpose.ROTATE_90)
        if flip == "h":
            img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        elif flip == "v":
            img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        tag = f"_g{angle}" if angle else ""
        tag += "_flipv" if flip == "v" else ("_fliph" if flip == "h" else "")
        outs.append(_save_out(img, src, workdir, tag))

    if len(outs) == 1:
        return outs
    return [make_zip(outs, workdir / "imagenes-giradas.zip")]


# ---------------------------------------------------------------- marca de agua
_POSITIONS = {
    "top-left": lambda W, H, w, h, m: (m, m),
    "top-center": lambda W, H, w, h, m: ((W - w) // 2, m),
    "top-right": lambda W, H, w, h, m: (W - w - m, m),
    "middle-left": lambda W, H, w, h, m: (m, (H - h) // 2),
    "center": lambda W, H, w, h, m: ((W - w) // 2, (H - h) // 2),
    "middle-right": lambda W, H, w, h, m: (W - w - m, (H - h) // 2),
    "bottom-left": lambda W, H, w, h, m: (m, H - h - m),
    "bottom-center": lambda W, H, w, h, m: ((W - w) // 2, H - h - m),
    "bottom-right": lambda W, H, w, h, m: (W - w - m, H - h - m),
}


@register(ToolMeta(
    id="watermark-image", name="Marca de agua imagen", category="imagen",
    description="Estampa texto sobre tus fotos: posición, transparencia y color configurables.",
    multiple=True, accept=WIDE, output_hint="imagen(es) con marca de agua", icon="droplet",
    options=[
        {"name": "text", "label": "Texto", "type": "text", "default": "© Mi Marca", "placeholder": "Texto de la marca"},
        {"name": "position", "label": "Posición", "type": "select",
         "choices": [{"value": k, "label": k.replace("-", " ").replace("middle", "medio").replace("top", "arriba").replace("bottom", "abajo").replace("left", "izq").replace("right", "der").replace("center", "centro")}
                     for k in ["top-left", "top-center", "top-right", "middle-left", "center", "middle-right", "bottom-left", "bottom-center", "bottom-right"]],
         "default": "bottom-right"},
        {"name": "opacity", "label": "Opacidad (%)", "type": "number", "default": 50, "min": 5, "max": 100},
        {"name": "size", "label": "Tamaño de fuente (px)", "type": "number", "default": 48, "min": 10, "max": 400},
        {"name": "color", "label": "Color (hex)", "type": "text", "default": "#ffffff"},
    ],
))
def watermark_image(files: List[Path], options: dict, workdir: Path) -> List[Path]:
    files = filter_by_accept(files, WIDE)
    text = str(options.get("text") or "").strip()
    if not text:
        raise ToolError("Escribe el texto de la marca de agua")
    position = str(options.get("position") or "bottom-right")
    opacity = max(0.05, min(1.0, int(options.get("opacity", 50)) / 100))
    size = int(options.get("size") or 48)
    color = _hex_rgb(str(options.get("color") or "#ffffff"))

    outs = []
    for src in files:
        img = Image.open(src).convert("RGBA")
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        font = _load_font(size)
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        margin = max(12, int(min(img.size) * 0.03))
        x, y = _POSITIONS.get(position, _POSITIONS["bottom-right"])(img.width, img.height, tw, th, margin)
        # sombra sutil para legibilidad
        draw.text((x + 2, y + 2), text, font=font, fill=(0, 0, 0, int(opacity * 160)))
        draw.text((x, y), text, font=font, fill=(*color, int(opacity * 255)))
        combined = Image.alpha_composite(img, overlay).convert("RGB") if src.suffix.lower() in (".jpg", ".jpeg") \
            else Image.alpha_composite(img, overlay)
        outs.append(_save_out(combined, src, workdir, "_marca"))

    if len(outs) == 1:
        return outs
    return [make_zip(outs, workdir / "imagenes-marca-agua.zip")]


# ---------------------------------------------------------------- convertir a JPG
@register(ToolMeta(
    id="convert-to-jpg", name="Convertir a JPG", category="imagen",
    description="Convierte por lotes PNG, WEBP, GIF, BMP, TIFF o HEIC/HEIF (iPhone) a JPG.",
    multiple=True, accept=CONVERTIBLE, output_hint="JPG(s)", icon="fileimage",
    options=[
        {"name": "background", "label": "Fondo para transparencias", "type": "select",
         "choices": [{"value": "white", "label": "Blanco"}, {"value": "black", "label": "Negro"}],
         "default": "white"},
        {"name": "quality", "label": "Calidad", "type": "number", "default": 90, "min": 40, "max": 100},
    ],
))
def convert_to_jpg(files: List[Path], options: dict, workdir: Path) -> List[Path]:
    files = filter_by_accept(files, CONVERTIBLE)
    bg = _hex_rgb("#000000" if options.get("background") == "black" else "#ffffff")
    quality = int(options.get("quality") or 90)

    try:
        from pillow_heif import register_heif_opener
        register_heif_opener()
    except ImportError:
        pass  # HEIC fallará con mensaje claro si aparece

    outs = []
    for src in files:
        try:
            img = Image.open(src)
        except Exception:
            raise ToolError(f"No pude leer '{src.name}'. Si es HEIC verifica que sea un archivo válido.")
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            base = Image.new("RGB", img.size, bg)
            base.paste(img, mask=img.split()[-1])
            img = base
        else:
            img = img.convert("RGB")
        out = workdir / f"{safe_stem(src.name)}.jpg"
        img.save(out, format="JPEG", quality=quality)
        outs.append(out)

    if len(outs) == 1:
        return outs
    return [make_zip(outs, workdir / "imagenes-jpg.zip")]


# ---------------------------------------------------------------- meme
@register(ToolMeta(
    id="create-meme", name="Crear meme", category="imagen",
    description="Texto clásico de meme arriba y abajo, con contorno negro automático.",
    multiple=False, accept=COMMON + [".gif"], output_hint="imagen lista para compartir", icon="laugh",
    options=[
        {"name": "top_text", "label": "Texto superior", "type": "text", "placeholder": "TEXTO ARRIBA"},
        {"name": "bottom_text", "label": "Texto inferior", "type": "text", "placeholder": "TEXTO ABAJO"},
        {"name": "size_pct", "label": "Tamaño del texto (%)", "type": "number", "default": 10,
         "min": 4, "max": 25, "help": "% del ancho de la imagen"},
    ],
))
def create_meme(files: List[Path], options: dict, workdir: Path) -> List[Path]:
    src = single(filter_by_accept(files, COMMON + [".gif"]), "Crear meme")
    top = str(options.get("top_text") or "").strip().upper()
    bottom = str(options.get("bottom_text") or "").strip().upper()
    if not top and not bottom:
        raise ToolError("Escribe al menos un texto para el meme")

    img = Image.open(src).convert("RGBA")
    draw = ImageDraw.Draw(img)
    W = img.width
    size = max(14, int(W * float(options.get("size_pct") or 10) / 100))
    font = _load_font(size)
    stroke = max(2, size // 12)
    margin = int(W * 0.03)

    def put(txt, anchor_y_top: bool):
        nonlocal_draw = ImageDraw.Draw(img)
        lines = _wrap(nonlocal_draw, txt, font, W - margin * 2)
        line_h = size + int(size * 0.25)
        total_h = line_h * len(lines)
        y = margin if anchor_y_top else img.height - total_h - margin
        for ln in lines:
            bb = nonlocal_draw.textbbox((0, 0), ln, font=font, stroke_width=stroke)
            lw = bb[2] - bb[0]
            nonlocal_draw.text(((W - lw) // 2, y), ln, font=font,
                               fill=(255, 255, 255, 255), stroke_width=stroke,
                               stroke_fill=(0, 0, 0, 255))
            y += line_h

    if top:
        put(top, True)
    if bottom:
        put(bottom, False)

    out = workdir / f"{safe_stem(src.name)}_meme.png"
    img.save(out)
    return [out]


def _wrap(draw, text, font, max_w):
    words = text.split()
    if not words:
        return [""]
    lines, cur = [], words[0]
    for w in words[1:]:
        trial = f"{cur} {w}"
        if draw.textbbox((0, 0), trial, font=font)[2] <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


# ---------------------------------------------------------------- pixelar caras
@register(ToolMeta(
    id="pixelate-faces", name="Pixelar caras", category="imagen",
    description="Detecta rostros y los pixela automáticamente. También sirve para ocultar información privada.",
    multiple=True, accept=COMMON, output_hint="imagen(es) con caras pixeladas", icon="grid",
    options=[
        {"name": "pixel", "label": "Tamaño del pixelado (%)", "type": "number", "default": 8,
         "min": 2, "max": 30, "help": "% del ancho de la cara detectada"},
        {"name": "mode", "label": "Efecto", "type": "select",
         "choices": [{"value": "pixelate", "label": "Pixelado"}, {"value": "blur", "label": "Desenfoque"}],
         "default": "pixelate"},
    ],
))
def pixelate_faces(files: List[Path], options: dict, workdir: Path) -> List[Path]:
    files = filter_by_accept(files, COMMON)
    try:
        import cv2
    except ImportError:
        raise ToolError("Detector facial no disponible en este despliegue")

    pct = int(options.get("pixel") or 8) / 100.0
    mode = str(options.get("mode") or "pixelate")
    cascade_path = str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml")
    cascade = cv2.CascadeClassifier(cascade_path)

    outs = []
    any_face = False
    for src in files:
        img = Image.open(src).convert("RGB")
        cv_img = cv2.cvtColor(__import__("numpy").array(img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, scaleFactor=1.12, minNeighbors=5, minSize=(36, 36))
        if len(faces) == 0:
            continue
        any_face = True
        for (x, y, fw, fh) in faces:
            pad = int(fw * 0.08)
            x0, y0 = max(0, x - pad), max(0, y - pad)
            x1, y1 = min(img.width, x + fw + pad), min(img.height, y + fh + pad)
            region = img.crop((x0, y0, x1, y1))
            if mode == "blur":
                region = region.filter(ImageFilter.GaussianBlur(max(6, int(fw * 0.18))))
            else:
                small = max(1, int(region.width * pct))
                tiny = region.resize((small, max(1, int(region.height * small / region.width))), Image.NEAREST)
                region = tiny.resize(region.size, Image.NEAREST)
            img.paste(region, (x0, y0))
        out = _save_out(img, src, workdir, "_pixelete")
        outs.append(out)

    if not any_face:
        raise ToolError("No se detectaron caras. Prueba con la foto más cercana y frontal.")
    if len(outs) == 1:
        return outs
    return [make_zip(outs, workdir / "caras-pixeladas.zip")]


# ---------------------------------------------------------------- ampliar
@register(ToolMeta(
    id="upscale-image", name="Ampliar imagen rápido", category="imagen",
    description="Aumenta 2x o 4x con LANCZOS. Es rápido y no usa IA.",
    multiple=True, accept=COMMON, output_hint="imagen(es) ampliada(s)", icon="zoom",
    options=[
        {"name": "factor", "label": "Factor", "type": "select",
         "choices": [{"value": "2", "label": "2x"}, {"value": "4", "label": "4x"}],
         "default": "2"},
        {"name": "sharpen", "label": "Enfoque posterior", "type": "switch", "default": True},
    ],
))
def upscale_image(files: List[Path], options: dict, workdir: Path) -> List[Path]:
    files = filter_by_accept(files, COMMON)
    factor = int(options.get("factor") or 2)
    sharpen = bool(options.get("sharpen", True))

    outs = []
    for src in files:
        img = Image.open(src)
        nw, nh = img.width * factor, img.height * factor
        up = img.resize((nw, nh), Image.LANCZOS)
        if sharpen:
            from PIL import ImageEnhance
            up = up.filter(ImageFilter.UnsharpMask(radius=2, percent=110, threshold=3))
            up = ImageEnhance.Contrast(up).enhance(1.02)
        out = workdir / f"{safe_stem(src.name)}_{factor}x.png"
        up.save(out, optimize=True)
        outs.append(out)

    if len(outs) == 1:
        return outs
    return [make_zip(outs, workdir / "imagenes-ampliadas.zip")]
