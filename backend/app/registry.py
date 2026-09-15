"""Registro central de herramientas.

Para agregar una herramienta nueva:
1. Crea backend/tools/<id>.py con una función `run(files, options, workdir) -> list[Path]`.
2. Agrega su ToolMeta a TOOLS aquí (o usa @register).
"""
from dataclasses import dataclass, field
from typing import Callable, List
from pathlib import Path
import importlib


@dataclass
class ToolMeta:
    id: str
    name: str
    description: str
    category: str  # "pdf" | "imagen"
    multiple: bool
    accept: List[str]
    output_hint: str
    icon: str
    options: List[dict] = field(default_factory=list)
    ui_mode: str = "generic"
    ai: bool = False


@dataclass
class RegisteredTool:
    meta: ToolMeta
    handler: Callable


REGISTRY: dict[str, RegisteredTool] = {}


def register(meta: ToolMeta):
    def deco(fn):
        REGISTRY[meta.id] = RegisteredTool(meta=meta, handler=fn)
        return fn
    return deco


def load_all():
    """Importa todos los módulos de tools para que se registren solos."""
    pkg_dir = Path(__file__).parent.parent / "tools"
    for f in sorted(pkg_dir.glob("*.py")):
        if f.name.startswith("_"):
            continue
        importlib.import_module(f"tools.{f.stem}")


def get(tool_id: str) -> RegisteredTool | None:
    return REGISTRY.get(tool_id)


def list_metas() -> list[dict]:
    return [asdict(t.meta) for t in sorted(REGISTRY.values(), key=lambda x: x.meta.id)]


def asdict(meta: ToolMeta) -> dict:
    return {
        "id": meta.id,
        "name": meta.name,
        "description": meta.description,
        "category": meta.category,
        "multiple": meta.multiple,
        "accept": meta.accept,
        "output_hint": meta.output_hint,
        "icon": meta.icon,
        "options": meta.options,
        "ui_mode": meta.ui_mode,
        "ai": meta.ai,
    }
