"""Generate fashion dataset via OpenRouter (dùng chính CHAT_MODEL để gọi).

Chạy:
    cd backend
    python scripts/generate_dataset.py
"""
from __future__ import annotations

import asyncio
import json
import random
import re
import sys
from pathlib import Path
from typing import Any

# cho phép chạy từ /home/.../backend với `python scripts/generate_dataset.py`
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openai import AsyncOpenAI  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.log import configure_logging, logger  # noqa: E402
from app.schemas import Product  # noqa: E402

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
PRODUCTS_FILE = DATA_DIR / "products.jsonl"

# Số lượng từng category (random, không đều)
CATEGORY_DISTRIBUTION: dict[str, int] = {
    "áo": 14,
    "quần": 8,
    "váy": 6,
    "giày": 5,
    "phụ kiện": 18,
    "đồ thể thao": 9,
}

BRANDS = [
    "Maison Étoile",
    "Linh & Co",
    "Phố Studio",
    "Urban Roots",
    "Đóa",
    "Hoa Sen Atelier",
    "Mây Boutique",
    "Sài Gòn Retro",
    "Hà Nội Minimal",
    "Biển Collective",
    "Sunset Denim",
    "Lụa Lam",
]

SIZES_CLOTHING = ["S", "M", "L", "XL", "XXL"]
SIZES_SHOES = ["36", "37", "38", "39", "40", "41", "42", "43", "44"]
SIZES_ACCESSORY = ["Free"]

COLORS_FASHION = [
    "trắng", "đen", "be", "xám", "xanh navy", "xanh mint", "đỏ đô",
    "hồng pastel", "vàng mustard", "nâu", "kem", "xanh olive",
    "cam đất", "xanh dương", "rêu",
]

MATERIALS_BY_CATEGORY = {
    "áo": ["cotton 100%", "linen", "lụa", "voan", "polyester pha cotton", "modal"],
    "quần": ["jean denim", "kaki", "linen", "cotton pha", "vải dù"],
    "váy": ["voan", "lụa", "cotton", "linen", "ren"],
    "giày": ["da bò thật", "da tổng hợp", "canvas", "vải mesh"],
    "phụ kiện": ["da bò", "da PU", "vải canvas", "kim loại mạ vàng", "nhựa cao cấp", "len mềm"],
    "đồ thể thao": ["polyester thấm hút", "spandex pha cotton", "mesh thoáng khí", "nylon"],
}

CATEGORY_GENDER_HINT = {
    "áo": ["nữ", "nam", "unisex"],
    "quần": ["nam", "nữ", "unisex"],
    "váy": ["nữ"],
    "giày": ["unisex", "nam", "nữ"],
    "phụ kiện": ["nữ", "unisex"],
    "đồ thể thao": ["unisex", "nam", "nữ"],
}

PRICE_RANGE_VND = {
    "áo": (180_000, 1_200_000),
    "quần": (250_000, 1_500_000),
    "váy": (300_000, 2_000_000),
    "giày": (450_000, 3_500_000),
    "phụ kiện": (80_000, 1_500_000),
    "đồ thể thao": (200_000, 1_800_000),
}


SYSTEM_PROMPT = """Bạn là trợ lý tạo dữ liệu mẫu cho cửa hàng thời trang Việt Nam. Sinh 1 sản phẩm JSON theo schema.

Yêu cầu:
- Tên sản phẩm tiếng Việt tự nhiên, phù hợp danh mục và giới tính.
- Mô tả 2-3 câu, nhấn mạnh chất liệu, dịp sử dụng, phong cách.
- Từ khoá (tags): 5-8 từ khoá tiếng Việt ngắn gọn để tìm kiếm (vd "mùa hè", "công sở", "basic", "dạo phố").
- KHÔNG bao gồm trường id, image_url, created_at (chúng được thêm tự động).

Chỉ trả về JSON hợp lệ, KHÔNG kèm markdown code block, KHÔNG giải thích thêm."""


USER_TEMPLATE = """Sinh 1 sản phẩm thời trang với các ràng buộc:

- Danh mục: {category}
- Thương hiệu: {brand}
- Giới tính: {gender_hint}
- Chất liệu gợi ý: {material_suggest}
- Tầm giá (VND): {price_low} - {price_high}
- Size gợi ý: {size_suggest}
- Màu gợi ý: {color_suggest}

Trả JSON với các trường:
{{
  "name": "...",
  "brand": "{brand}",
  "category": "{category}",
  "description": "...",
  "price_vnd": <số nguyên trong khoảng trên>,
  "sizes_available": [...],
  "colors": [...],
  "material": "...",
  "stock_per_size": {{"size": số_lượng, ...}},
  "tags": [...],
  "gender": "{gender_hint}"
}}
"""


def _extract_json(content: str) -> dict[str, Any]:
    """LLM có thể wrap JSON trong ```json ... ```; strip trước khi parse."""
    content = content.strip()
    # remove leading/trailing code fences
    content = re.sub(r"^```(?:json)?\s*", "", content)
    content = re.sub(r"\s*```$", "", content)
    # nếu có nhiều JSON, lấy object đầu tiên
    m = re.search(r"\{.*\}", content, re.DOTALL)
    if m:
        content = m.group(0)
    return json.loads(content)


async def generate_one(
    client: AsyncOpenAI,
    category: str,
    brand: str,
    semaphore: asyncio.Semaphore,
) -> Product | None:
    gender_hint = random.choice(CATEGORY_GENDER_HINT[category])
    material_suggest = random.choice(MATERIALS_BY_CATEGORY[category])
    price_low, price_high = PRICE_RANGE_VND[category]
    size_pool = SIZES_SHOES if category == "giày" else (SIZES_ACCESSORY if category == "phụ kiện" else SIZES_CLOTHING)
    n_choices = max(1, min(random.randint(2, 4), len(size_pool)))
    size_choices = random.sample(size_pool, k=n_choices)
    size_suggest = ", ".join(size_choices)
    color_suggest = random.choice(COLORS_FASHION)

    user_msg = USER_TEMPLATE.format(
        category=category,
        brand=brand,
        gender_hint=gender_hint,
        material_suggest=material_suggest,
        price_low=price_low,
        price_high=price_high,
        size_suggest=size_suggest,
        color_suggest=color_suggest,
    )

    async with semaphore:
        try:
            resp = await client.chat.completions.create(
                model=get_settings().chat_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.9,
                max_tokens=500,
            )
            content = resp.choices[0].message.content or ""
            data = _extract_json(content)
            # validate & thêm field tự động
            data.setdefault("brand", brand)
            data.setdefault("category", category)
            data.setdefault("gender", gender_hint)
            return Product(
                id="",  # assigned later
                name=data["name"],
                brand=data["brand"],
                category=data["category"],
                description=data["description"],
                price_vnd=int(data["price_vnd"]),
                sizes_available=data["sizes_available"],
                colors=data["colors"],
                material=data["material"],
                stock_per_size={k: int(v) for k, v in data["stock_per_size"].items()},
                tags=data["tags"],
                image_url="",
                gender=data["gender"],
            )
        except Exception as e:
            logger.error(f"Generate fail for {category}/{brand}: {e}")
            return None


async def main():
    configure_logging()
    s = get_settings()
    if not s.openrouter_api_key:
        logger.error("OPENROUTER_API_KEY rỗng. Cấu hình .env trước.")
        sys.exit(1)

    client = AsyncOpenAI(
        api_key=s.openrouter_api_key,
        base_url=s.base_url,
        default_headers={
            "HTTP-Referer": s.http_referer,
            "X-Title": s.x_title,
        },
    )

    semaphore = asyncio.Semaphore(3)  # tránh 429 free tier
    tasks = []
    for category, count in CATEGORY_DISTRIBUTION.items():
        for _ in range(count):
            brand = random.choice(BRANDS)
            tasks.append(generate_one(client, category, brand, semaphore))

    logger.info(f"Đang sinh {len(tasks)} sản phẩm...")
    results = await asyncio.gather(*tasks)
    products: list[Product] = [p for p in results if p is not None]
    if len(products) < len(tasks):
        logger.warning(f"Chỉ sinh thành công {len(products)}/{len(tasks)} sản phẩm")

    # gán id + image_url
    for i, p in enumerate(products, start=1):
        pid = f"P{i:04d}"
        p.id = pid
        p.image_url = f"https://picsum.photos/seed/{pid}/400/400"

    # ghi JSONL
    with PRODUCTS_FILE.open("w", encoding="utf-8") as f:
        for p in products:
            f.write(p.model_dump_json() + "\n")

    logger.info(f"Đã ghi {len(products)} sản phẩm vào {PRODUCTS_FILE}")
    logger.info("Tiếp theo: python scripts/build_embeddings.py")


if __name__ == "__main__":
    asyncio.run(main())
