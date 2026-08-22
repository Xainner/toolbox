"""Herramientas de seguridad PDF: watermark, protect, unlock."""
from __future__ import annotations

import io
from pathlib import Path
from typing import List

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject

from tools.common import ToolError, safe_stem, filter_by_accept, single
from app.registry import ToolMeta, register
from tools.pdf_tools import make_zip

PDF = [".pdf"]


@register(ToolMeta(
    id="watermark-pdf", name="Marca de agua", category="pdf",
    description="Estampa un texto sobre todas las páginas del PDF.",
    multiple=True, accept=PDF, output_hint="PDF con marca de agua", icon="droplet",
    options=[
        {"name": "text", "label": "Texto", "type": "text", "default": "CONFIDENCIAL", "placeholder": "Texto de la marca"},
        {"name": "opacity", "label": "Opacidad (%)", "type": "number", "default": 20, "min": 5, "max": 100},
        {"name": "rotate", "label": "Inclinación", "type": "select",
         "choices": [{"value": "45", "label": "Diagonal (45°)"}, {"value": "0", "label": "Horizontal"}],
         "default": "45"},
        {"name": "size", "label": "Tamaño de fuente", "type": "number", "default": 48, "min": 10, "max": 120},
    ],
))
def watermark_pdf(files: List[Path], options: dict, workdir: Path) -> List[Path]:
    files = filter_by_accept(files, PDF)
    text = str(options.get("text") or "").strip()
    if not text:
        raise ToolError("Escribe el texto de la marca de agua")
    opacity = max(0.05, min(1.0, int(options.get("opacity", 20)) / 100))
    rotation = int(options.get("rotate", "45"))
    font_size = int(options.get("size", 48))

    outs = []
    for src in files:
        reader = PdfReader(src)
        writer = PdfWriter()
        for page in reader.pages:
            pw = float(page.mediabox.width)
            ph = float(page.mediabox.height)
            packet = _watermark_pdf_bytes(text, pw, ph, opacity, rotation, font_size)
            wm_reader = PdfReader(packet)
            page.merge_page(wm_reader.pages[0])
            writer.add_page(page)
        out = workdir / f"{safe_stem(src.name)}_marca.pdf"
        with open(out, "wb") as fh:
            writer.write(fh)
        outs.append(out)

    if len(outs) == 1:
        return outs
    return [make_zip(outs, workdir / "pdfs-marca-agua.zip")]


def _watermark_pdf_bytes(text: str, w: float, h: float, opacity: float, rotation: int, size: int):
    """Genera una página-watermark en memoria con reportlab si está, si no con pypdf puro."""
    try:
        from reportlab.pdfgen import canvas
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=(w, h))
        c.setFont("Helvetica-Bold", size)
        c.setFillColorRGB(0.4, 0.4, 0.4, alpha=opacity)
        c.saveState()
        c.translate(w / 2, h / 2)
        c.rotate(rotation)
        c.drawCentredString(0, -size / 3, text)
        c.restoreState()
        c.showPage()
        c.save()
        buf.seek(0)
        return buf
    except ImportError:
        raise ToolError("Motor de marcas no disponible en este despliegue")


@register(ToolMeta(
    id="protect-pdf", name="Proteger PDF", category="pdf",
    description="Cifra el PDF con contraseña para restringir su apertura y edición.",
    multiple=True, accept=PDF, output_hint="PDF cifrado", icon="lock",
    options=[
        {"name": "password", "label": "Contraseña", "type": "text", "placeholder": "Contraseña del documento"},
    ],
))
def protect_pdf(files: List[Path], options: dict, workdir: Path) -> List[Path]:
    files = filter_by_accept(files, PDF)
    password = str(options.get("password") or "")
    if len(password) < 3:
        raise ToolError("Escribe una contraseña de al menos 3 caracteres")

    outs = []
    for src in files:
        reader = PdfReader(src)
        if reader.is_encrypted:
            raise ToolError(f"'{src.name}' ya está protegido")
        writer = PdfWriter(clone_from=reader)
        writer.encrypt(user_password=password, owner_password=password + "_owner",
                       algorithm="AES-128")
        out = workdir / f"{safe_stem(src.name)}_protegido.pdf"
        with open(out, "wb") as fh:
            writer.write(fh)
        outs.append(out)

    if len(outs) == 1:
        return outs
    return [make_zip(outs, workdir / "pdfs-protegidos.zip")]


@register(ToolMeta(
    id="unlock-pdf", name="Desbloquear PDF", category="pdf",
    description="Quita la protección de un PDF si conoces su contraseña.",
    multiple=False, accept=PDF, output_hint="PDF sin restricciones", icon="unlock",
    options=[
        {"name": "password", "label": "Contraseña actual", "type": "text", "placeholder": "Déjalo vacío si solo tiene restricciones de dueño"},
    ],
))
def unlock_pdf(files: List[Path], options: dict, workdir: Path) -> List[Path]:
    src = single(filter_by_accept(files, PDF), "Desbloquear PDF")
    password = str(options.get("password") or "")
    reader = PdfReader(src)

    if not reader.is_encrypted:
        # Sin cifrado real: igual regeneramos limpio
        writer = PdfWriter(clone_from=reader)
        out = workdir / f"{safe_stem(src.name)}_desbloqueado.pdf"
        with open(out, "wb") as fh:
            writer.write(fh)
        return [out]

    try:
        result = reader.decrypt(password)
    except Exception:
        raise ToolError("No se pudo descifrar el archivo — revisa la contraseña")
    if result == 0 or result is False:
        raise ToolError("Contraseña incorrecta")

    writer = PdfWriter(clone_from=reader)
    out = workdir / f"{safe_stem(src.name)}_desbloqueado.pdf"
    with open(out, "wb") as fh:
        writer.write(fh)
    return [out]
