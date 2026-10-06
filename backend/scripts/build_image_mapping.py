"""Build mapping giữa image folder và product bằng embedding similarity.

Workflow:
  1. Đọc 53 folder names trong frontend/public/stitch_fashion_product_image_generator/
  2. Đọc 53 products từ data/products.jsonl
  3. Embed folder_repr = folder_name + " " + image_url_hint
  4. Embed product_repr = product.name + " " + product.description + " " + product.tags
  5. Cosine similarity matrix → greedy 1-1 matching (ưu tiên cặp score cao nhất)
  6. In preview table ra terminal
  7. Ghi data/image_mapping.json

KHÔNG chạy update_image_urls.py. User sẽ review thủ công.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app.log import configure_logging, logger  # noqa: E402
from app.rag.embedder import Embedder  # noqa: E402
from app.schemas import Product  # noqa: E402
REPO_ROOT = Path(__file__).resolve().parents[2]  # btl_ttnt_hai/
IMG_DIR = REPO_ROOT / "frontend" / "public" / "stitch_fashion_product_image_generator"
PRODUCTS_FILE = REPO_ROOT / "backend" / "data" / "products.jsonl"
MAPPING_FILE = REPO_ROOT / "backend" / "data" / "image_mapping.json"


def _humanize_folder(folder: str) -> str:
    """Folder name kiểu 'high_end_men_s_fashion_product_photography_of_an_olive_green_100_natural_silk'
    → human readable 'men fashion product photography of an olive green 100 natural silk'."""
    return folder.replace("_", " ").strip()


def _load_products() -> list[Product]:
    if not PRODUCTS_FILE.exists():
        logger.error(f"{PRODUCTS_FILE} không tồn tại.")
        raise SystemExit(1)
    out: list[Product] = []
    with PRODUCTS_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(Product.model_validate_json(line))
    return out


def _load_folders() -> list[str]:
    if not IMG_DIR.exists():
        logger.error(f"{IMG_DIR} không tồn tại.")
        raise SystemExit(1)
    return sorted(p.name for p in IMG_DIR.iterdir() if p.is_dir())


def _cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity. Embedder trả list[float] đã normalized hay không — tính explicit."""
    import math

    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


async def _embed_all(texts: list[str]) -> list[list[float]]:
    """Gọi Embedder (OpenRouter + fallback local). Không thay đổi provider."""
    embedder = Embedder()
    logger.info(f"Embedding {len(texts)} texts qua {embedder.backend}...")
    return await embedder.embed(texts)


def _greedy_match(
    sims: list[list[float]], folder_names: list[str], products: list[Product]
) -> dict[str, str]:
    """Greedy 1-1 matching: tại mỗi bước chọn cặp (i, j) có sim chưa gán cao nhất."""
    n = len(folder_names)
    assert len(products) == n, f"folder count ({n}) != product count ({len(products)})"

    used_folders: set[int] = set()
    used_products: set[int] = set()
    pairs: list[tuple[float, int, int]] = []  # (sim, folder_idx, product_idx)

    for i in range(n):
        for j in range(n):
            pairs.append((sims[i][j], i, j))
    pairs.sort(key=lambda x: -x[0])

    folder_to_product_idx: dict[int, int] = {}
    for sim, i, j in pairs:
        if i in used_folders or j in used_products:
            continue
        used_folders.add(i)
        used_products.add(j)
        folder_to_product_idx[i] = j
        if len(used_folders) == n:
            break

    return {products[folder_to_product_idx[i]].id: folder_names[i] for i in range(n)}


async def main() -> None:
    configure_logging()
    products = _load_products()
    folders = _load_folders()

    logger.info(f"Đọc {len(products)} products, {len(folders)} folders.")
    if len(products) != len(folders):
        logger.warning("Counts lệch nhau! Script sẽ match theo min count.")

    n = min(len(products), len(folders))
    products = products[:n]
    folders = folders[:n]

    # Build texts
    folder_texts = [_humanize_folder(f) for f in folders]
    product_texts = [
        f"{p.name}. {p.description}. Tags: {' '.join(p.tags)}" for p in products
    ]

    # Embed (batch all at once cho nhanh)
    folder_vecs = await _embed_all(folder_texts)
    product_vecs = await _embed_all(product_texts)

    # Cosine sim matrix
    sims: list[list[float]] = [[_cosine(a, b) for b in product_vecs] for a in folder_vecs]

    # Greedy match
    mapping = _greedy_match(sims, folders, products)

    # Preview table
    logger.info("=" * 100)
    logger.info(f"{'PID':6s} | {'Product':40s} | {'Folder':60s} | {'Score':6s}")
    logger.info("-" * 100)
    # Match score cho từng cặp trong mapping
    folder_idx_of = {f: i for i, f in enumerate(folders)}
    product_idx_of = {p.id: i for i, p in enumerate(products)}
    for pid in sorted(mapping.keys(), key=lambda x: int(x[1:])):
        folder = mapping[pid]
        fi = folder_idx_of[folder]
        pi = product_idx_of[pid]
        score = sims[fi][pi]
        pname = products[pi].name[:38]
        folder_disp = folder[:58]
        logger.info(f"{pid:6s} | {pname:40s} | {folder_disp:60s} | {score:.3f}")
    logger.info("=" * 100)

    # Score distribution
    all_scores = [sims[i][j] for i in range(n) for j in range(n)]
    matched_scores = [
        sims[folder_idx_of[mapping[p.id]]][product_idx_of[p.id]]
        for p in products
        if p.id in mapping
    ]
    logger.info(f"Score stats: min={min(all_scores):.3f} max={max(all_scores):.3f} mean={sum(all_scores)/len(all_scores):.3f}")
    logger.info(f"Matched scores: min={min(matched_scores):.3f} max={max(matched_scores):.3f} mean={sum(matched_scores)/len(matched_scores):.3f}")

    # Ghi file (sorted by product id)
    sorted_mapping = dict(sorted(mapping.items()))
    MAPPING_FILE.parent.mkdir(parents=True, exist_ok=True)
    with MAPPING_FILE.open("w", encoding="utf-8") as f:
        json.dump(sorted_mapping, f, ensure_ascii=False, indent=2)
        f.write("\n")
    logger.info(f"Đã ghi {MAPPING_FILE} ({len(sorted_mapping)} entries).")


if __name__ == "__main__":
    asyncio.run(main())
