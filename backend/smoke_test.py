"""Smoke test del backend: ejercita las herramientas con archivos reales."""
import io
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

WORK = Path(__file__).parent / "_smoke"
if WORK.exists():
    shutil.rmtree(WORK)
WORK.mkdir(parents=True)

# ---------- fixtures ----------
from PIL import Image, ImageDraw

img1 = WORK / "a.png"
img2 = WORK / "b.png"
for name, color in [("a.png", (200, 60, 60)), ("b.png", (60, 120, 220))]:
    im = Image.new("RGB", (400, 300), color)
    d = ImageDraw.Draw(im)
    d.ellipse([100, 60, 300, 240], fill=(255, 255, 255))
    im.save(WORK / name)

jpg = WORK / "c.jpg"
Image.new("RGB", (500, 350), (30, 160, 90)).save(jpg)

from reportlab.pdfgen import canvas as rl_canvas

def make_pdf(name: str, pages: int) -> Path:
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(300, 200))
    for i in range(pages):
        c.setFont("Helvetica", 20)
        c.drawString(50, 100, f"{name} pagina {i+1}")
        c.showPage()
    c.save()
    p = WORK / name
    p.write_bytes(buf.getvalue())
    return p

pdf3 = make_pdf("tres.pdf", 5)

from app.registry import load_all, REGISTRY

load_all()
print(f"== {len(REGISTRY)} herramientas registradas ==")
for tid in sorted(REGISTRY):
    print(" -", tid)

results = {}

def run(tool_id, files, options=None):
    wd = WORK / f"out_{tool_id}"
    wd.mkdir(exist_ok=True)
    out = REGISTRY[tool_id].handler(files, options or {}, wd)
    sizes = [p.stat().st_size for p in out]
    assert all(p.exists() and p.stat().st_size > 100 for p in out), f"{tool_id}: salida vacía"
    results[tool_id] = [p.name for p in out]
    print(f"OK {tool_id:16s} -> {[n for n in results[tool_id]]} {sizes}")
    return out

# PDF
run("merge-pdf", [make_pdf("p1.pdf", 2), make_pdf("p2.pdf", 3)])
outs = run("split-pdf", [pdf3], {"mode": "ranges", "ranges": "1-2, 4"})
run("split-pdf", [pdf3], {"mode": "every_page"})
run("rotate-pdf", [pdf3], {"angle": "180"})
run("compress-pdf", [pdf3], {"quality": "low"})
run("watermark-pdf", [pdf3], {"text": "SECRETO", "opacity": 25})
prot = run("protect-pdf", [pdf3], {"password": "1234"})
run("unlock-pdf", prot, {"password": "1234"})
run("unlock-pdf", [pdf3], {"password": ""})  # sin cifrar
run("jpg-to-pdf", [img1, img2, jpg], {"margin": 10, "pagesize": "fit"})
run("jpg-to-pdf", [img1], {"margin": 0, "pagesize": "a4", "orientation": "landscape"})
run("pdf-to-jpg", [pdf3], {"dpi": "96"})

# Imagen
run("convert-image", [img1, jpg], {"format": "webp", "quality": 80})
run("compress-image", [img1, jpg], {"quality": 60, "scale": 75})
run("resize-image", [img1, jpg], {"mode": "percent", "width": 50, "height": 50, "keep_ratio": True})
run("resize-image", [jpg], {"mode": "pixels", "width": 200, "height": None, "keep_ratio": True})

# Errores esperados
from tools.common import ToolError

def expect_error(tool_id, files, options, why):
    try:
        wd = WORK / f"err_{tool_id}"
        wd.mkdir(exist_ok=True)
        REGISTRY[tool_id].handler(files, options, wd)
        raise AssertionError(f"{tool_id} debía fallar ({why})")
    except ToolError as e:
        print(f"OK error-esperado {tool_id}: {e}")

expect_error("merge-pdf", [pdf3], {}, "un solo archivo")
expect_error("split-pdf", [pdf3], {"mode": "ranges", "ranges": "99-120"}, "rango inválido")
expect_error("convert-image", [pdf3], {"format": "png"}, "tipo incorrecto")
expect_error("protect-pdf", [pdf3], {"password": "x"}, "contraseña corta")

# remove-bg: solo si rembg está instalado localmente
try:
    import rembg  # noqa
    HAS_REMBG = True
except ImportError:
    HAS_REMBG = False

if HAS_REMBG:
    run("remove-bg", [img1], {"post": "transparent"})
    run("remove-bg", [jpg], {"post": "white"})
else:
    print("SKIP remove-bg (rembg no instalado en local; se prueba en Docker)")

print(f"\nSMOKE OK · {len(results)} tools ejecutadas sin errores")
