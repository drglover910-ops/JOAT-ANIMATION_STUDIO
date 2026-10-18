from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
ASSETS_ROOT = ROOT / "assets"

CHARACTERS = {
    "CHAR-003": "Densín",
    "CHAR-004": "Cristu",
    "CHAR-005": "Guenièvre / Jen",
    "CHAR-006": "Hasley",
    "CHAR-007": "Ms. LaveRen",
}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def inspect_image(path: Path) -> dict:
    with Image.open(path) as image:
        width, height = image.size

    relative_path = path.relative_to(ROOT).as_posix()

    return {
        "filename": path.name,
        "path": relative_path,
        "sha256": sha256_file(path),
        "width": width,
        "height": height,
    }


def main():
    output = {
        "generator": "J.O.A.T. Character Asset Master",
        "characters": {},
    }

    total_assets = 0

    for character_id, character_name in CHARACTERS.items():
        folder = ASSETS_ROOT / character_id

        print(f"\n{'=' * 72}")
        print(f"{character_id} — {character_name}")
        print(f"{'=' * 72}")

        if not folder.exists():
            print(f"ERROR: Missing folder: {folder}")
            output["characters"][character_id] = {
                "name": character_name,
                "error": "folder_missing",
                "assets": [],
            }
            continue

        files = sorted(
            path
            for path in folder.iterdir()
            if path.is_file()
            and path.suffix.lower() in IMAGE_EXTENSIONS
        )

        records = []

        for index, path in enumerate(files, start=1):
            try:
                metadata = inspect_image(path)

                record = {
                    "asset_id": f"{character_id}-A{index:02d}",
                    **metadata,
                }

                records.append(record)
                total_assets += 1

                print(json.dumps(record, indent=2, ensure_ascii=False))

            except Exception as exc:
                print(f"ERROR reading {path.name}: {exc}")

        output["characters"][character_id] = {
            "name": character_name,
            "asset_count": len(records),
            "assets": records,
        }

        print(f"\nAsset count: {len(records)}")

    output_path = ROOT / "generated_character_metadata.json"

    output_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"\n{'=' * 72}")
    print("COMPLETE")
    print(f"Total inspected assets: {total_assets}")
    print(f"Metadata written to: {output_path.name}")
    print(f"{'=' * 72}")


if __name__ == "__main__":
    main()