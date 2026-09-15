"""Compara el recorte anterior con el preset de alta calidad.

Estructura esperada:

    dataset/images/producto.png
    dataset/masks/producto.png

Las máscaras de referencia deben ser imágenes en escala de grises con fondo 0 y
primer plano 255. El script descarga los modelos de rembg la primera vez.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.registry import REGISTRY, load_all  # noqa: E402


def metrics(prediction: Path, truth: Path) -> dict[str, float]:
    pred = np.asarray(Image.open(prediction).convert("L"), dtype=np.float32) / 255.0
    target = np.asarray(
        Image.open(truth).convert("L").resize((pred.shape[1], pred.shape[0])),
        dtype=np.float32,
    ) / 255.0
    mae = float(np.mean(np.abs(pred - target)))
    pred_fg = pred >= 0.5
    true_fg = target >= 0.5
    tp = int(np.count_nonzero(pred_fg & true_fg))
    fp = int(np.count_nonzero(pred_fg & ~true_fg))
    fn = int(np.count_nonzero(~pred_fg & true_fg))
    f_score = (2 * tp) / max(1, 2 * tp + fp + fn)
    return {"mae": round(mae, 6), "f_score": round(f_score, 6)}


def run_variant(image: Path, workdir: Path, options: dict[str, object]) -> Path:
    workdir.mkdir(parents=True, exist_ok=True)
    REGISTRY["remove-bg"].handler([image], options, workdir)
    mask = workdir / "mascara.png"
    if not mask.exists():
        raise RuntimeError(f"No se generó máscara para {image.name}")
    return mask


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--output", type=Path, default=Path("background-benchmark.json"))
    args = parser.parse_args()
    images_dir = args.dataset / "images"
    masks_dir = args.dataset / "masks"
    images = sorted(path for path in images_dir.iterdir() if path.is_file())
    if not images:
        raise SystemExit("El dataset no contiene imágenes")

    load_all()
    results: list[dict[str, object]] = []
    temp_root = Path(tempfile.mkdtemp(prefix="toolbox-bg-benchmark-"))
    try:
        for index, image in enumerate(images):
            truth = masks_dir / f"{image.stem}.png"
            if not truth.exists():
                raise SystemExit(f"Falta la máscara de referencia: {truth}")
            legacy = run_variant(
                image,
                temp_root / f"{index}-legacy",
                {"preset": "balanced", "edge_mode": "none", "binary_mask": True},
            )
            quality = run_variant(
                image,
                temp_root / f"{index}-quality",
                {"preset": "quality", "edge_mode": "decontaminate", "binary_mask": False},
            )
            results.append(
                {"image": image.name, "legacy": metrics(legacy, truth), "quality": metrics(quality, truth)}
            )
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)

    summary: dict[str, object] = {"images": results}
    for variant in ("legacy", "quality"):
        summary[variant] = {
            key: round(float(np.mean([row[variant][key] for row in results])), 6)
            for key in ("mae", "f_score")
        }
    args.output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
