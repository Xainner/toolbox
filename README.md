# App3 Toolbox

Herramientas self-hosted para PDF e imágenes — estilo iLovePDF + Photoroom. Todo corre en tu red: los archivos no salen de casa3090.

## Stack

- **Frontend**: React 19 + Vite + TypeScript + Tailwind CSS 4 + shadcn/ui
  - Motion (animaciones) · Lucide (iconos) · TanStack Table v8 + Recharts (actividad)
  - React Hook Form + zod (formularios dinámicos) · Sonner (toasts) · cmdk (paleta `Ctrl+K`)
  - react-resizable-panels · dnd-kit (reordenar archivos drag & drop)
- **Backend**: FastAPI + registro dinámico de herramientas
  - PDF: pypdf, pikepdf, img2pdf, pymupdf, reportlab
  - Imagen: Pillow + rembg (u2netp, IA local para quitar fondos)

## Herramientas incluidas

| Categoría | Herramienta | Qué hace |
|---|---|---|
| PDF | Unir PDF | Combina varios PDF en el orden que definas |
| PDF | Dividir PDF | Por rangos (`1-3, 5`) o página por página |
| PDF | Comprimir PDF | Re-muestrea imágenes internas |
| PDF | Rotar PDF | 90° / 180° / 270° |
| PDF | JPG a PDF | Imágenes → PDF con márgenes y tamaño A4/ajustado |
| PDF | PDF a JPG | Cada página a imagen |
| PDF | Marca de agua | Texto con opacidad e inclinación configurables |
| PDF | Proteger / Desbloquear | Cifrado AES con contraseña |
| Imagen | Quitar fondo (IA) | rembg local → PNG transparente o color sólido |
| Imagen | Convertir imagen | JPG ↔ PNG ↔ WEBP |
| Imagen | Comprimir imagen | Calidad + reescalado |
| Imagen | Redimensionar | Por % o píxeles, manteniendo proporción |

## Agregar una herramienta nueva

1. Crea `backend/tools/mi_tool.py`:

```python
from pathlib import Path
from typing import List
from app.registry import ToolMeta, register
from tools.common import ToolError

@register(ToolMeta(
    id="mi-tool", name="Mi herramienta", category="pdf",
    description="Qué hace.", multiple=False, accept=[".pdf"],
    output_hint="un PDF", icon="archive",
    options=[{"name": "factor", "label": "Factor", "type": "number", "default": 2}],
))
def mi_tool(files: List[Path], options: dict, workdir: Path) -> List[Path]:
    out = workdir / "salida.pdf"
    out.write_bytes(files[0].read_bytes())
    return [out]
```

2. Si usa un icono nuevo, agrégalo a `TOOL_ICONS` en `frontend/src/lib/types.ts`.
3. Reinicia la API. El catálogo (`GET /api/tools`), el formulario y la página se generan solos.

El frontend arma la UI leyendo la metadata del backend: dropzone, opciones tipadas (select/number/text/switch), validación zod y descarga son genéricas.

## Desarrollo local

```bash
# Backend
cd backend
uv venv .venv && uv pip install --python .venv -r requirements.txt
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000   # Linux/Mac: .venv/bin/python

# Frontend
cd frontend
npm install
npm run dev        # http://localhost:5173 (proxia /api al :8000)
```

Smoke test del backend: `.venv/Scripts/python smoke_test.py`

## Producción (casa3090)

```bash
docker compose up -d --build   # web en :3090
```

- `web` (nginx): sirve el build de Vite y proxia `/api/` → `api:8000`
- `api`: FastAPI; guarda jobs en `./data/jobs/<id>` y stats en SQLite `./data/app3.db`
- Límite de subida: 200 MB por trabajo; nginx acepta hasta 220 MB
