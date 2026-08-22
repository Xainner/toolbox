"""Utilidades compartidas por las herramientas."""
from __future__ import annotations

from pathlib import Path
from typing import List


def ext_of(name: str) -> str:
    return Path(name).suffix.lower()


def safe_stem(name: str) -> str:
    stem = Path(name).stem
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in stem)[:80] or "file"


def filter_by_accept(files: List[Path], accept: List[str]) -> List[Path]:
    ok = [f for f in files if ext_of(f.name) in {a.lower() for a in accept}]
    bad = [f.name for f in files if f not in ok]
    if bad:
        raise ToolError(f"Formato no soportado: {', '.join(bad)}. Aceptados: {', '.join(accept)}")
    return ok


class ToolError(Exception):
    """Error con mensaje amigable para el usuario."""


def single(files: List[Path], tool: str) -> Path:
    if len(files) != 1:
        raise ToolError(f"{tool} espera exactamente 1 archivo (recibí {len(files)})")
    return files[0]
