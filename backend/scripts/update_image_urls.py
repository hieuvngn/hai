"""Update products.jsonl image_url to local stitch paths using image_mapping.json.

Usage: python backend/scripts/update_image_urls.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
DATA_DIR = BACKEND_DIR / "data"
IMAGE_MAPPING_FILE = DATA_DIR / "image_mapping.json"
PRODUCTS_FILE = DATA_DIR / "products.jsonl"
FRONTEND_PUBLIC_DIR = BACKEND_DIR.parent / "frontend" / "public" / "stitch_fashion_product_image_generator"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update product image URLs to local paths")
    parser.add_argument("--dry-run", action="store_true", help="Do not write file, just print what would change")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not IMAGE_MAPPING_FILE.exists():
        print(f"ERROR: {IMAGE_MAPPING_FILE} not found. Required file missing.", file=sys.stderr)
        sys.exit(1)

    try:
        with IMAGE_MAPPING_FILE.open("r", encoding="utf-8") as f:
            mapping: dict[str, str] = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"ERROR: Failed to read {IMAGE_MAPPING_FILE}: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(mapping, dict):
        print(f"ERROR: {IMAGE_MAPPING_FILE} must be a JSON object mapping product ID to folder name.", file=sys.stderr)
        sys.exit(1)

    if not PRODUCTS_FILE.exists():
        print(f"ERROR: {PRODUCTS_FILE} not found.", file=sys.stderr)
        sys.exit(1)

    raw_text = PRODUCTS_FILE.read_text(encoding="utf-8")
    has_trailing_newline = raw_text.endswith("\n") if raw_text else True
    raw_lines = raw_text.splitlines()

    updated_count = 0
    skipped_count = 0
    warned_count = 0

    new_lines: list[str] = []

    for raw_line in raw_lines:
        stripped = raw_line.strip()
        if not stripped:
            new_lines.append(raw_line)
            continue

        try:
            product = json.loads(stripped)
        except json.JSONDecodeError:
            new_lines.append(raw_line)
            skipped_count += 1
            continue

        pid = product.get("id")
        if pid is None:
            new_lines.append(raw_line)
            skipped_count += 1
            continue

        folder = mapping.get(pid)
        if folder is None:
            new_lines.append(raw_line)
            skipped_count += 1
            continue

        new_image_url = f"/stitch_fashion_product_image_generator/{folder}/screen.png"

        folder_path = FRONTEND_PUBLIC_DIR / folder
        if not folder_path.is_dir():
            print(f"WARNING: Folder missing for {pid} -> {folder_path}", file=sys.stderr)
            warned_count += 1

        if product.get("image_url") != new_image_url:
            product["image_url"] = new_image_url
            new_line = json.dumps(product, ensure_ascii=False)
            new_lines.append(new_line)
            updated_count += 1
            if args.dry_run:
                print(f"Would update {pid}: {new_image_url}")
        else:
            # Already correct — keep original line as-is
            new_lines.append(raw_line)
            # Count as not updated (already correct), but for idempotency second run will show 0 updated
            # This is intentional: updated = actually changed

    summary = f"Updated {updated_count} products, skipped {skipped_count} (no mapping), warned {warned_count} (folder missing)"
    print(summary)

    if args.dry_run:
        return

    tmp_path = PRODUCTS_FILE.with_suffix(".jsonl.tmp")
    output_text = "\n".join(new_lines)
    if has_trailing_newline and output_text and not output_text.endswith("\n"):
        output_text += "\n"
    tmp_path.write_text(output_text, encoding="utf-8")
    os.replace(tmp_path, PRODUCTS_FILE)


if __name__ == "__main__":
    main()
