"""OCR, organización visual de PDF y ampliación real con IA."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List

from PIL import Image
from pypdf import PdfReader, PdfWriter

from app.registry import ToolMeta, register
from tools.common import ToolError, filter_by_accept, safe_stem, single
from tools.pdf_tools import make_zip


@register(ToolMeta(
    id="ocr-pdf", name="OCR a PDF buscable", category="pdf",
    description="Reconoce texto en documentos escaneados en español e inglés, sin salir de tu servidor.",
    multiple=True, accept=[".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff"],
    output_hint="PDF/A buscable", icon="scantext", ai=True,
    options=[
        {"name": "language", "label": "Idioma", "type": "select", "default": "spa+eng",
         "choices": [{"value": "spa+eng", "label": "Español + inglés"},
                     {"value": "spa", "label": "Español"}, {"value": "eng", "label": "Inglés"}]},
        {"name": "rotate", "label": "Corregir orientación", "type": "switch", "default": True},
        {"name": "deskew", "label": "Enderezar páginas", "type": "switch", "default": True},
        {"name": "sidecar", "label": "Incluir texto .txt", "type": "switch", "default": False,
         "advanced": True},
        {"name": "image_dpi", "label": "DPI de imágenes", "type": "number", "default": 300,
         "min": 72, "max": 600, "advanced": True,
         "help": "solo aplica cuando subes imágenes en vez de PDF"},
    ],
))
def ocr_pdf(files: List[Path], options: dict, workdir: Path) -> List[Path]:
    accepted = [".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff"]
    files = filter_by_accept(files, accepted)
    if not files:
        raise ToolError("Agrega al menos un PDF o imagen")
    try:
        import ocrmypdf
    except ImportError as exc:
        raise ToolError("OCRmyPDF no está disponible en este despliegue") from exc

    outputs = []
    image_dpi = int(options.get("image_dpi") or 300)
    for src in files:
        out = workdir / f"{safe_stem(src.name)}_buscable.pdf"
        sidecar = workdir / f"{safe_stem(src.name)}_texto.txt" if options.get("sidecar") else None
        call_kwargs = {
            "language": [p for p in str(options.get("language") or "spa+eng").split("+")],
            "rotate_pages": bool(options.get("rotate", True)),
            "deskew": bool(options.get("deskew", True)),
            "skip_text": True,
            "output_type": "pdfa",
            "sidecar": sidecar,
            "progress_bar": False,
        }
        # OCRmyPDF exige --image-dpi cuando la entrada es una imagen sin DPI
        # en sus metadatos (capturas de pantalla, fotos, etc).
        if src.suffix.lower() != ".pdf":
            call_kwargs["image_dpi"] = image_dpi
        try:
            ocrmypdf.ocr(src, out, **call_kwargs)
        except Exception as exc:
            raise ToolError(f"No se pudo aplicar OCR a {src.name}: {exc}") from exc
        outputs.append(out)
    if len(outputs) == 1:
        return outputs
    extras = outputs + list(workdir.glob("*_texto.txt"))
    return [make_zip(extras, workdir / "documentos-ocr.zip")]


@register(ToolMeta(
    id="organize-pdf", name="Organizar PDF", category="pdf",
    description="Reordena, rota, elimina o extrae páginas con miniaturas antes de crear el PDF.",
    multiple=False, accept=[".pdf"], output_hint="PDF reorganizado", icon="panels",
    ui_mode="pdf_organizer",
    options=[],
))
def organize_pdf(files: List[Path], options: dict, workdir: Path) -> List[Path]:
    src = single(filter_by_accept(files, [".pdf"]), "Organizar PDF")
    reader = PdfReader(src)
    operations = options.get("pages")
    if isinstance(operations, str):
        try:
            operations = json.loads(operations)
        except json.JSONDecodeError as exc:
            raise ToolError("La lista de páginas es inválida") from exc
    if not operations:
        operations = [{"index": i, "rotation": 0} for i in range(len(reader.pages))]
    writer = PdfWriter()
    for item in operations:
        index = int(item.get("index", -1))
        if index < 0 or index >= len(reader.pages):
            raise ToolError(f"Página fuera de rango: {index + 1}")
        page = reader.pages[index]
        rotation = int(item.get("rotation", 0)) % 360
        if rotation:
            page.rotate(rotation)
        writer.add_page(page)
    if len(writer.pages) == 0:
        raise ToolError("El documento debe conservar al menos una página")
    out = workdir / f"{safe_stem(src.name)}_organizado.pdf"
    with open(out, "wb") as output:
        writer.write(output)
    return [out]


_UPSCALERS: dict[str, object] = {}


def _get_upscaler(model_name: str, factor: int):
    cache_key = f"{model_name}-{factor}"
    if cache_key in _UPSCALERS:
        return _UPSCALERS[cache_key]
    try:
        import sys
        import torch
        import torchvision.transforms.functional as tv_functional
        sys.modules.setdefault("torchvision.transforms.functional_tensor", tv_functional)
        from basicsr.archs.rrdbnet_arch import RRDBNet
        from basicsr.utils.download_util import load_file_from_url
        from realesrgan import RealESRGANer
    except ImportError as exc:
        raise ToolError("Real-ESRGAN no está disponible; instala el perfil de IA") from exc

    if model_name == "anime":
        scale, blocks = 4, 6
        filename = "RealESRGAN_x4plus_anime_6B.pth"
        url = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth"
    elif factor == 2:
        scale, blocks = 2, 23
        filename = "RealESRGAN_x2plus.pth"
        url = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth"
    else:
        scale, blocks = 4, 23
        filename = "RealESRGAN_x4plus.pth"
        url = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth"
    model_dir = Path(os.getenv("REALESRGAN_HOME", os.getenv("U2NET_HOME", "/srv/models")))
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = load_file_from_url(url=url, model_dir=str(model_dir), file_name=filename, progress=True)
    model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=blocks, num_grow_ch=32, scale=scale)
    upscaler = RealESRGANer(scale=scale, model_path=model_path, model=model, tile=256, tile_pad=16,
                           pre_pad=0, half=torch.cuda.is_available(), gpu_id=0 if torch.cuda.is_available() else None)
    _UPSCALERS[cache_key] = upscaler
    return upscaler


@register(ToolMeta(
    id="upscale-ai", name="Ampliar con IA", category="imagen",
    description="Recupera detalle y resolución con Real-ESRGAN local, en CPU o NVIDIA GPU.",
    multiple=True, accept=[".jpg", ".jpeg", ".png", ".webp"],
    output_hint="imagen ampliada con IA", icon="sparkles", ui_mode="image_compare", ai=True,
    options=[
        {"name": "factor", "label": "Factor", "type": "select", "default": "2",
         "choices": [{"value": "2", "label": "2x · recomendado"}, {"value": "4", "label": "4x"}]},
        {"name": "model", "label": "Contenido", "type": "select", "default": "general",
         "choices": [{"value": "general", "label": "Fotos y gráficos"},
                     {"value": "anime", "label": "Anime e ilustración"}]},
    ],
))
def upscale_ai(files: List[Path], options: dict, workdir: Path) -> List[Path]:
    files = filter_by_accept(files, [".jpg", ".jpeg", ".png", ".webp"])
    factor = int(options.get("factor") or 2)
    model_name = str(options.get("model") or "general")
    upscaler = _get_upscaler(model_name, factor)
    try:
        import cv2
    except ImportError as exc:
        raise ToolError("OpenCV no está disponible") from exc
    outputs = []
    for src in files:
        image = cv2.imread(str(src), cv2.IMREAD_UNCHANGED)
        if image is None:
            raise ToolError(f"No se pudo leer {src.name}")
        try:
            result, _ = upscaler.enhance(image, outscale=factor)
        except RuntimeError as exc:
            if "memory" in str(exc).lower():
                raise ToolError("Memoria insuficiente para ampliar; prueba 2x o una imagen menor") from exc
            raise
        out = workdir / f"{safe_stem(src.name)}_ia_{factor}x.png"
        cv2.imwrite(str(out), result)
        outputs.append(out)
    if len(outputs) == 1:
        return outputs
    return [make_zip(outputs, workdir / "imagenes-ampliadas-ia.zip")]
