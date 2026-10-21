"""Rebuild state PNGs/GIF from saved rasters without executing model steps."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from PIL import Image

from brmangue_studio.figure_exports import read_state_preview, save_state_map


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--language", choices=("en", "pt-BR"), default="en")
    args = parser.parse_args()
    metadata = json.loads((args.run_dir / "metadata.json").read_text())
    inputs = metadata["input_metadata"]
    if isinstance(inputs, str):
        inputs = json.loads((args.run_dir / inputs).read_text())
    catalog = metadata["model_state_catalog"]
    trajectory = pd.read_csv(args.run_dir / "trajectory.csv")
    state_dir = args.output_dir / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    layouts, paths = [], []
    for row in trajectory.to_dict(orient="records"):
        year = int(row["calendar_year"])
        image, geometry = read_state_preview(args.run_dir / "states" / f"state_{year}.tif", inputs["grid"])
        present = {int(code) for code in catalog["states"] if int(row.get(f"class_{code}", 0)) > 0}
        destination = state_dir / f"state_{year}.png"
        layouts.append(save_state_map(image, catalog, year, destination, language=args.language,
                                      present_codes=present, geometry=geometry))
        paths.append(destination)
        if len(paths) % 10 == 0:
            print(json.dumps({"figures_rebuilt": len(paths)}), flush=True)
    width = height = 0
    for path in paths:
        with Image.open(path) as image:
            width, height = max(width, image.width), max(height, image.height)
    frames = []
    for path in paths:
        with Image.open(path) as image:
            canvas = Image.new("RGB", (width, height), "white")
            canvas.paste(image.convert("RGB"), (0, 0))
            frames.append(canvas.convert("P", palette=Image.Palette.ADAPTIVE))
    if frames:
        frames[0].save(args.output_dir / "state.gif", save_all=True, append_images=frames[1:],
                       duration=800, loop=0, optimize=False)
    result = {"source_run": str(args.run_dir), "new_model_steps": 0,
              "language": args.language, "layouts": layouts, "frames": len(paths)}
    (args.output_dir / "layout_verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"figures_rebuilt": len(paths), "new_model_steps": 0}))


if __name__ == "__main__":
    main()
