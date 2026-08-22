"""Herramientas PDF: merge, split, compress, rotate, jpg2pdf, pdf2jpg, watermark, protect, unlock."""
from __future__ import annotations

import io
import json
from pathlib import Path
from typing import List

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject

from tools.common import ToolError, safe_stem, filter_by_accept, single
from app.registry import ToolMeta, register

PDF = [".pdf"]


@register(ToolMeta(
    id="merge-pdf", name="Unir PDF", category="pdf",
    description="Combina varios PDF en un solo documento, en el orden que quieras.",
    multiple=True, accept=PDF, output_hint="un PDF combinado", icon="combine",
))
def merge_pdf(files: List[Path], options: dict, workdir: Path) -> List[Path]:
    files = filter_by_accept(files, PDF)
    if len(files) < 2:
        raise ToolError("Necesito al menos 2 PDF para unir")
    writer = PdfWriter()
    for p in files:
        reader = PdfReader(p)
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:
                raise ToolError(f"'{p.name}' está protegido con contraseña — usa Desbloquear PDF primero")
        for page in reader.pages:
            writer.add_page(page)
    out = workdir / "combinado.pdf"
    with open(out, "wb") as fh:
        writer.write(fh)
    return [out]


@register(ToolMeta(
    id="split-pdf", name="Dividir PDF", category="pdf",
    description="Separa un PDF en archivos individuales o por rangos de páginas.",
    multiple=False, accept=PDF, output_hint="ZIP o PDF según el modo", icon="scissors",
    options=[
        {"name": "mode", "label": "Modo", "type": "select",
         "choices": [{"value": "ranges", "label": "Rangos de páginas"}, {"value": "every_page", "label": "Cada página por separado"}],
         "default": "ranges"},
        {"name": "ranges", "label": "Rangos", "type": "text",
         "placeholder": "1-3, 5, 8-10", "help": "Solo en modo rangos. Separa con comas."},
    ],
))
def split_pdf(files: List[Path], options: dict, workdir: Path) -> List[Path]:
    src = single(filter_by_accept(files, PDF), "Dividir PDF")
    reader = PdfReader(src)
    n = len(reader.pages)
    mode = options.get("mode", "ranges")

    def parse_ranges(txt: str) -> list[list[int]]:
        groups = []
        for part in txt.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                a, b = part.split("-", 1)
                lo, hi = int(a), int(b)
            else:
                lo = hi = int(part)
            if lo < 1 or hi > n or lo > hi:
                raise ToolError(f"Rango inválido: '{part}' (el documento tiene {n} páginas)")
            groups.append(list(range(lo - 1, hi)))
        if not groups:
            raise ToolError("Especifica al menos un rango, ej: 1-3, 5")
        return groups

    outs = []
    if mode == "every_page":
        for i in range(n):
            w = PdfWriter()
            w.add_page(reader.pages[i])
            op = workdir / f"pagina_{i + 1:03d}.pdf"
            with open(op, "wb") as fh:
                w.write(fh)
            outs.append(op)
    else:
        ranges_txt = str(options.get("ranges") or "")
        if not ranges_txt.strip():
            raise ToolError("Indica los rangos de páginas, ej: 1-3, 5")
        for gi, pages in enumerate(parse_ranges(ranges_txt), 1):
            w = PdfWriter()
            for pi in pages:
                w.add_page(reader.pages[pi])
            op = workdir / f"parte_{gi}.pdf"
            with open(op, "wb") as fh:
                w.write(fh)
            outs.append(op)

    if len(outs) == 1:
        return outs
    zip_path = make_zip(outs, workdir / "pdf-dividido.zip")
    return [zip_path]


def make_zip(paths: List[Path], dest: Path) -> Path:
    import zipfile
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in paths:
            zf.write(p, arcname=p.name)
    return dest


@register(ToolMeta(
    id="compress-pdf", name="Comprimir PDF", category="pdf",
    description="Reduce el peso del PDF re-muestreando imágenes internas.",
    multiple=True, accept=PDF, output_hint="PDF más liviano", icon="archive",
    options=[
        {"name": "quality", "label": "Calidad de imagen", "type": "select",
         "choices": [
             {"value": "high", "label": "Alta (menor compresión)"},
             {"value": "medium", "label": "Media (recomendado)"},
             {"value": "low", "label": "Baja (mínimo peso)"},
         ],
         "default": "medium"},
    ],
))
def compress_pdf(files: List[Path], options: dict, workdir: Path) -> List[Path]:
    files = filter_by_accept(files, PDF)
    quality = options.get("quality", "medium")
    dpi_map = {"high": 150, "medium": 100, "low": 72}
    zoom = {"high": 0.6, "medium": 0.45, "low": 0.3}[quality]

    outs = []
    for src in files:
        try:
            import pikepdf
            with pikepdf.open(src, allow_overwriting_input=True) as pdf:
                pdf.save(workdir / "_tmp.pdf", compress_streams=True,
                         object_stream_mode=pikepdf.ObjectStreamMode.generate,
                         recompress_flate=True)
                tmp_out = workdir / "_tmp.pdf"
                base_size = tmp_out.stat().st_size
                candidate = tmp_out
                # Re-muestreo real de imágenes vía Pillow sobre objetos XObject
                from PIL import Image
                import zlib
                doc = pikepdf.open(tmp_out)
                for page in doc.pages:
                    res = page.get("/Resources", None)
                    if res is None or "/XObject" not in res:
                        continue
                    xobjs = res["/XObject"]
                    for key in list(xobjs.keys()):
                        obj = xobjs[key]
                        try:
                            if obj.get("/Subtype") != pikepdf.Name("/Image"):
                                continue
                            w, h = int(obj["/Width"]), int(obj["/Height"])
                            if w * h < 40000:
                                continue
                            filt = obj.get("/Filter", None)
                            if filt is not None and "/DCTDecode" in str(filt):
                                raw = obj.read_bytes()
                                img = Image.open(io.BytesIO(raw))
                                img = img.convert("RGB")
                                nw, nh = max(1, int(w * zoom)), max(1, int(h * zoom))
                                img = img.resize((nw, nh), Image.LANCZOS)
                                buf = io.BytesIO()
                                img.save(buf, format="JPEG", quality={"high": 80, "medium": 65, "low": 50}[quality])
                                new_obj = doc.make_stream(buf.getvalue())
                                new_obj[NameObject("/Type")] = NameObject("/XObject")
                                new_obj[NameObject("/Subtype")] = NameObject("/Image")
                                new_obj[NameObject("/Width")] = nw
                                new_obj[NameObject("/Height")] = nh
                                new_obj[NameObject("/ColorSpace")] = pikepdf.Name("/DeviceRGB")
                                new_obj[NameObject("/BitsPerComponent")] = 8
                                new_obj[NameObject("/Filter")] = pikepdf.Name("/DCTDecode")
                                xobjs[key] = new_obj
                        except Exception:
                            continue
                final = workdir / f"{safe_stem(src.name)}_comprimido.pdf"
                doc.save(final, compress_streams=True)
                doc.close()
                outs.append(final if final.stat().st_size < src.stat().st_size else _fallback_compress(src, final))
        except ImportError:
            outs.append(_fallback_compress(src, workdir / f"{safe_stem(src.name)}_comprimido.pdf"))

    if len(outs) == 1:
        return outs
    return [make_zip(outs, workdir / "pdfs-comprimidos.zip")]


def _fallback_compress(src: Path, dest: Path) -> Path:
    """Compresión sin re-muestreo: solo streams + object streams."""
    import pikepdf
    with pikepdf.open(src) as pdf:
        pdf.save(dest, compress_streams=True,
                 object_stream_mode=pikepdf.ObjectStreamMode.generate,
                 recompress_flate=True)
    return dest


@register(ToolMeta(
    id="rotate-pdf", name="Rotar PDF", category="pdf",
    description="Rota todas las páginas del PDF (90°, 180°, 270°).",
    multiple=True, accept=PDF, output_hint="PDF rotado", icon="rotate",
    options=[
        {"name": "angle", "label": "Ángulo", "type": "select",
         "choices": [{"value": "90", "label": "90° derecha"}, {"value": "180", "label": "180°"}, {"value": "270", "label": "90° izquierda"}],
         "default": "90"},
    ],
))
def rotate_pdf(files: List[Path], options: dict, workdir: Path) -> List[Path]:
    files = filter_by_accept(files, PDF)
    angle = int(options.get("angle", "90"))
    outs = []
    for src in files:
        reader = PdfReader(src)
        w = PdfWriter()
        for page in reader.pages:
            page.rotate(angle)
            w.add_page(page)
        out = workdir / f"{safe_stem(src.name)}_rotado.pdf"
        with open(out, "wb") as fh:
            w.write(fh)
        outs.append(out)
    if len(outs) == 1:
        return outs
    return [make_zip(outs, workdir / "pdfs-rotados.zip")]


@register(ToolMeta(
    id="jpg-to-pdf", name="JPG a PDF", category="pdf",
    description="Convierte imágenes (JPG/PNG/WEBP) en un PDF. El orden de las imágenes define las páginas.",
    multiple=True, accept=[".jpg", ".jpeg", ".png", ".webp"],
    output_hint="un PDF con una página por imagen", icon="fileimage",
    options=[
        {"name": "margin", "label": "Margen (mm)", "type": "number", "default": 10, "min": 0, "max": 40},
        {"name": "pagesize", "label": "Tamaño de página", "type": "select",
         "choices": [{"value": "fit", "label": "Ajustar a la imagen"}, {"value": "a4", "label": "A4"}],
         "default": "fit"},
        {"name": "orientation", "label": "Orientación (A4)", "type": "select",
         "choices": [{"value": "auto", "label": "Automática"}, {"value": "portrait", "label": "Vertical"}, {"value": "landscape", "label": "Horizontal"}],
         "default": "auto"},
    ],
))
def jpg_to_pdf(files: List[Path], options: dict, workdir: Path) -> List[Path]:
    files = filter_by_accept(files, [".jpg", ".jpeg", ".png", ".webp"])
    if not files:
        raise ToolError("Agrega al menos una imagen")
    margin_mm = float(options.get("margin") or 0)
    pagesize = options.get("pagesize", "fit")
    orientation = options.get("orientation", "auto")

    from PIL import Image
    import img2pdf

    a4_portrait = (img2pdf.mm_to_pt(210), img2pdf.mm_to_pt(297))
    border = (img2pdf.mm_to_pt(margin_mm),) * 2 if margin_mm > 0 else None

    layout_args = {}
    if pagesize == "fit":
        if border:
            layout_args["border"] = border
    else:
        if orientation == "landscape":
            page_size = (a4_portrait[1], a4_portrait[0])  # 297x210
        else:
            page_size = a4_portrait  # vertical o auto
        try:
            layout_fn = img2pdf.get_layout_fun(page_size, border=border,
                                               auto_orient=(orientation == "auto"))
        except TypeError:  # versiones sin auto_orient
            layout_fn = img2pdf.get_layout_fun(page_size, border=border)
        layout_args["layout_fun"] = layout_fn

    out = workdir / "imagenes.pdf"
    with open(out, "wb") as fh:
        fh.write(img2pdf.convert([str(p) for p in files], **layout_args))
    return [out]


@register(ToolMeta(
    id="pdf-to-jpg", name="PDF a JPG", category="pdf",
    description="Convierte cada página del PDF en una imagen JPG.",
    multiple=False, accept=PDF, output_hint="ZIP con las páginas JPG", icon="images",
    options=[
        {"name": "dpi", "label": "Resolución (DPI)", "type": "select",
         "choices": [{"value": "96", "label": "96 · pantalla"}, {"value": "150", "label": "150 · calidad"}, {"value": "200", "label": "200 · alta"}],
         "default": "150"},
    ],
))
def pdf_to_jpg(files: List[Path], options: dict, workdir: Path) -> List[Path]:
    src = single(filter_by_accept(files, PDF), "PDF a JPG")
    dpi = int(options.get("dpi", "150"))
    try:
        import pymupdf as fitz  # pymupdf moderno
    except ImportError:
        import fitz  # fallback paquete viejo
    doc = fitz.open(src)
    outs = []
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    for i, page in enumerate(doc):
        pix = page.get_pixmap(matrix=mat)
        op = workdir / f"pagina_{i + 1:03d}.jpg"
        pix.save(str(op), jpg_quality=88)
        outs.append(op)
    doc.close()
    if not outs:
        raise ToolError("El PDF no tiene páginas")
    if len(outs) == 1:
        return outs
    return [make_zip(outs, workdir / "paginas-jpg.zip")]
