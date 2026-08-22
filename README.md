<p align="center">
  <img src="docs/logo.png" width="140" alt="Toolbox">
</p>

<h1 align="center">Toolbox</h1>

<p align="center">
  <strong>Herramientas para PDF e imágenes, self-hosted.</strong><br>
  Estilo iLovePDF + Photoroom: tus archivos nunca salen de tu red.
</p>

<p align="center">
  <a href="#-caracter%C3%ADsticas"><img alt="Herramientas" src="https://img.shields.io/badge/herramientas-20-2563EB?style=for-the-badge"></a>
  <a href="#-instalaci%C3%B3n-con-docker"><img alt="Docker" src="https://img.shields.io/badge/docker-ready-2496ED?style=for-the-badge&logo=docker&logoColor=white"></a>
  <a href="LICENSE"><img alt="Licencia" src="https://img.shields.io/badge/licencia-MIT-10B981?style=for-the-badge"></a>
</p>

<p align="center">
  <img alt="React 19" src="https://img.shields.io/badge/React_19-Vite-TS-61DAFB?style=flat-square">
  <img alt="Tailwind 4" src="https://img.shields.io/badge/Tailwind_CSS-4-06B6D4?style=flat-square&logo=tailwindcss&logoColor=white">
  <img alt="shadcn/ui" src="https://img.shields.io/badge/shadcn%2Fui-componentes-black?style=flat-square">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-Python_3.12-009688?style=flat-square&logo=fastapi&logoColor=white">
  <img alt="rembg" src="https://img.shields.io/badge/rembg-IA_local-9333EA?style=flat-square">
  <img alt="PRs bienvenidos" src="https://img.shields.io/badge/PRs-bienvenidos-EC4899?style=flat-square">
</p>

---

**Unir · Dividir · Comprimir · Rotar · Convertir · Proteger · Quitar fondo con IA** — una app web
dockerizada que corre en tu propio servidor. Sin cuentas, sin límites artificiales, sin subir
nada a la nube de nadie más.

`Inicio • Herramientas • Stack • Instalación • Agregar herramientas • API • Licencia`

## ✨ Características

- **20 herramientas listas**: PDF (unir, dividir por rangos o páginas, comprimir, rotar,
  JPG↔PDF, marca de agua, proteger/desbloquear AES) e imagen (quitar fondo con IA local,
  convertir JPG/PNG/WEBP, comprimir, redimensionar).
- **Quitar fondo con IA de verdad**: modelos locales [rembg](https://github.com/danielgatis/rembg)
  seleccionables — ISNet (default), BiRefNet Lite y Portrait para retratos — con limpieza de
  máscara y *alpha matting* opcional para cabello y bordes finos.
- **Registro de herramientas extensible**: agregar una herramienta nueva es crear **un archivo**
  en `backend/tools/`; el catálogo, el formulario, la validación y la página se generan solos.
- **Drag & drop real**: reordena archivos antes de procesar (dnd-kit) — el resultado respeta tu orden.
- **Command palette `Ctrl+K`**, toasts (Sonner), animaciones (Motion), panel de actividad con
  gráficas (Recharts) e historial ordenable (TanStack Table).
- **100% self-hosted**: dos contenedores (nginx + FastAPI). Los modelos de IA se descargan una
  vez a un volumen persistente; después funcionan sin internet.

## 🧰 Herramientas incluidas

| | Herramienta | Qué hace |
|---|---|---|
| 📄 | **Unir PDF** | Combina varios PDF en el orden que definas |
| ✂️ | **Dividir PDF** | Por rangos (`1-3, 5`) o página por página (ZIP) |
| 🗜️ | **Comprimir PDF** | Re-muestreo de imágenes internas + flate |
| 🔄 | **Rotar PDF** | 90° / 180° / 270°, múltiples archivos |
| 🖼️ | **JPG a PDF** | Imágenes → PDF con márgenes y tamaño A4/ajustado |
| 📸 | **PDF a JPG** | Cada página a imagen (96–200 DPI) |
| 💧 | **Marca de agua** | Texto con opacidad, tamaño e inclinación configurables |
| 🔒 | **Proteger PDF** | Cifrado AES-128 con contraseña |
| 🔓 | **Desbloquear PDF** | Quita protección conocida la contraseña |
| 🪄 | **Quitar fondo (IA)** | ISNet/BiRefNet local → PNG transparente, blanco o color |
| ♻️ | **Convertir imagen** | JPG ↔ PNG ↔ WEBP |
| 📉 | **Comprimir imagen** | Calidad + reescalado, PNG→JPG automático |
| 📐 | **Redimensionar** | Por porcentaje o píxeles manteniendo proporción |
| ✂️ | **Recortar imagen** | Rectángulo definido en píxeles |
| 🔄 | **Girar imagen** | 90°/180°/270° y espejo horizontal/vertical en lote |
| 💧 | **Marca de agua imagen** | Texto con posición, color, tamaño y transparencia |
| 📥 | **Convertir a JPG** | PNG, WEBP, GIF, BMP, TIFF y **HEIC de iPhone** → JPG por lotes |
| 😄 | **Crear meme** | Texto clásico arriba/abajo con contorno automático |
| 🙈 | **Pixelar caras** | Detección facial local (OpenCV) + pixelado o desenfoque |
| 🔍 | **Ampliar imagen** | 2x / 4x con remuestreo LANCZOS y enfoque posterior |

## 🏗️ Arquitectura

```
┌───────────────────────────── docker compose ─────────────────────────────┐
│                                                                           │
│  ┌──────────┐   /api/*    ┌──────────────────────────┐                   │
│  │   web    ├────────────►│           api            │                   │
│  │  nginx   │             │  FastAPI + registro de   │                   │
│  │ Vite dist│◄────────────┤  herramientas (plugins)  │                   │
│  └──────────┘   download  └────────────┬─────────────┘                   │
│   :3090→80                             │                                  │
│                              ┌─────────▼─────────┐                        │
│                              │ ./data  ./models  │  volúmenes             │
│                              │ jobs   SQLite     │                        │
│                              └───────────────────┘                        │
└───────────────────────────────────────────────────────────────────────────┘
```

El frontend arma la UI **leyendo la metadata del backend** (`GET /api/tools`): dropzone según
tipos aceptados, formulario tipado (select/número/texto/switch) con zod, progreso y descarga.
El backend descubre los plugins escaneando `backend/tools/*.py`.

## 🚀 Instalación con Docker

Requisitos: Docker + Docker Compose.

```bash
git clone https://github.com/Xainner/toolbox.git
cd toolbox
docker compose up -d --build
```

Abre `http://localhost:3090`. Listo.

> Los modelos de IA se descargan automáticamente al primer uso (~4 MB el rápido, ~178 MB ISNet)
> y quedan persistidos en `./models/`. Las siguientes ejecuciones tardan segundos.

### Desarrollo local

```bash
# Backend (FastAPI en :8000)
cd backend
uv venv .venv && uv pip install --python .venv -r requirements.txt
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000   # Linux/Mac: .venv/bin/python

# Frontend (Vite en :5173, proxia /api → :8000)
cd frontend
npm install && npm run dev
```

Smoke test del backend: `python smoke_test.py` (ejercita las 20 herramientas con archivos generados).

## ➕ Agregar una herramienta nueva

1. Crea `backend/tools/mi_tool.py`:

```python
from pathlib import Path
from typing import List

from app.registry import ToolMeta, register


@register(ToolMeta(
    id="mi-tool", name="Mi herramienta", category="pdf",
    description="Qué hace.", multiple=False, accept=[".pdf"],
    output_hint="un PDF", icon="archive",
    options=[
        {"name": "factor", "label": "Factor", "type": "number", "default": 2},
    ],
))
def mi_tool(files: List[Path], options: dict, workdir: Path) -> List[Path]:
    out = workdir / "salida.pdf"
    out.write_bytes(files[0].read_bytes())
    return [out]
```

2. Reinicia la API (`docker compose restart api`). Nada más: catálogo, paleta `Ctrl+K`,
   formulario validado, página y descarga se generan desde la metadata.

Si el icono no existe en `frontend/src/lib/types.ts`, agrégalo ahí (Lucide).

## 🔌 API

| Endpoint | Método | Descripción |
|---|---|---|
| `/api/tools` | GET | Catálogo con metadata completa de cada herramienta |
| `/api/tools/{id}/run` | POST | multipart: `files[]` + `options` (JSON string) → job |
| `/api/download/{job_id}` | GET | Resultado del trabajo |
| `/api/stats` | GET | Historial de trabajos (SQLite) |
| `/api/health` | GET | Estado + número de herramientas |

Límite de subida: 200 MB por trabajo (configurable en `backend/app/main.py` y nginx).

## 🛠️ Stack

| Capa | Tecnología |
|---|---|
| UI | React 19 · Tailwind CSS 4 · shadcn/ui · Motion · Lucide |
| Interacción | cmdk (paleta) · Sonner (toasts) · dnd-kit (drag & drop) · react-resizable-panels |
| Formularios | React Hook Form + zod (generados dinámicamente) |
| Datos | TanStack Table v8 · Recharts |
| Backend | FastAPI · pypdf · pikepdf · pymupdf · img2pdf · reportlab · Pillow · rembg (ONNX) |
| Infra | Docker Compose · nginx · SQLite |

## 📄 Licencia

[MIT](LICENSE) © Xainner
