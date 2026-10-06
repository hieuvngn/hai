import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import type {
  AdminProductCreate,
  AdminProductUpdate,
  Product,
  Category,
  Gender,
} from "@/types";

const CATEGORIES: Category[] = [
  "áo",
  "quần",
  "váy",
  "giày",
  "phụ kiện",
  "đồ thể thao",
];
const GENDERS: Gender[] = ["nam", "nữ", "unisex"];

interface Props {
  initial?: Product;
  /** Payload form gửi lên — Create khi thêm, Update khi sửa. */
  onSubmit: (data: AdminProductCreate | AdminProductUpdate) => Promise<void>;
  onCancel?: () => void;
  submitLabel?: string;
}

export function ProductForm({
  initial,
  onSubmit,
  onCancel,
  submitLabel = "Lưu",
}: Props) {
  const [name, setName] = useState(initial?.name ?? "");
  const [brand, setBrand] = useState(initial?.brand ?? "");
  const [category, setCategory] = useState<Category>(initial?.category ?? "áo");
  const [gender, setGender] = useState<Gender>(initial?.gender ?? "unisex");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [priceVnd, setPriceVnd] = useState(initial?.price_vnd ?? 0);
  const [sizesAvailable, setSizesAvailable] = useState(
    (initial?.sizes_available ?? []).join(",")
  );
  const [colors, setColors] = useState((initial?.colors ?? []).join(", "));
  const [material, setMaterial] = useState(initial?.material ?? "");
  const [stockInput, setStockInput] = useState(() => {
    if (!initial) return "S:3,M:5,L:2";
    return Object.entries(initial.stock_per_size)
      .map(([k, v]) => `${k}:${v}`)
      .join(",");
  });
  const [tags, setTags] = useState((initial?.tags ?? []).join(", "));
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!initial) return;
    setName(initial.name);
    setBrand(initial.brand);
    setCategory(initial.category);
    setGender(initial.gender);
    setDescription(initial.description);
    setPriceVnd(initial.price_vnd);
    setSizesAvailable(initial.sizes_available.join(","));
    setColors(initial.colors.join(", "));
    setMaterial(initial.material);
    setStockInput(
      Object.entries(initial.stock_per_size)
        .map(([k, v]) => `${k}:${v}`)
        .join(",")
    );
    setTags(initial.tags.join(", "));
  }, [initial]);

  function parseStock(raw: string): Record<string, number> {
    const out: Record<string, number> = {};
    raw
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean)
      .forEach((pair) => {
        const [k, v] = pair.split(":").map((x) => x.trim());
        if (k && v && !Number.isNaN(Number(v))) out[k] = Number(v);
      });
    return out;
  }

  async function handleSubmit() {
    if (!name || !brand || !description) return;
    setSubmitting(true);
    try {
      await onSubmit({
        name,
        brand,
        category,
        gender,
        description,
        price_vnd: Number(priceVnd),
        sizes_available: sizesAvailable
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        colors: colors
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        material,
        stock_per_size: parseStock(stockInput),
        tags: tags
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
      });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <div className="space-y-2">
        <Label>Tên sản phẩm</Label>
        <Input value={name} onChange={(e) => setName(e.target.value)} />
      </div>
      <div className="space-y-2">
        <Label>Thương hiệu</Label>
        <Input value={brand} onChange={(e) => setBrand(e.target.value)} />
      </div>
      <div className="space-y-2">
        <Label>Danh mục</Label>
        <select
          className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
          value={category}
          onChange={(e) => setCategory(e.target.value as Category)}
        >
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </div>
      <div className="space-y-2">
        <Label>Giới tính</Label>
        <select
          className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
          value={gender}
          onChange={(e) => setGender(e.target.value as Gender)}
        >
          {GENDERS.map((g) => (
            <option key={g} value={g}>
              {g}
            </option>
          ))}
        </select>
      </div>
      <div className="md:col-span-2 space-y-2">
        <Label>Mô tả</Label>
        <Textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={3}
        />
      </div>
      <div className="space-y-2">
        <Label>Giá (VND)</Label>
        <Input
          type="number"
          value={priceVnd}
          onChange={(e) => setPriceVnd(Number(e.target.value))}
        />
      </div>
      <div className="space-y-2">
        <Label>Chất liệu</Label>
        <Input
          value={material}
          onChange={(e) => setMaterial(e.target.value)}
        />
      </div>
      <div className="md:col-span-2 space-y-2">
        <Label>Size có sẵn (phân cách dấu phẩy)</Label>
        <Input
          value={sizesAvailable}
          onChange={(e) => setSizesAvailable(e.target.value)}
          placeholder="S, M, L, XL"
        />
      </div>
      <div className="md:col-span-2 space-y-2">
        <Label>Tồn kho (size:số lượng, phân cách dấu phẩy)</Label>
        <Input
          value={stockInput}
          onChange={(e) => setStockInput(e.target.value)}
          placeholder="S:3, M:5, L:2"
        />
      </div>
      <div className="md:col-span-2 space-y-2">
        <Label>Màu sắc (phân cách dấu phẩy)</Label>
        <Input
          value={colors}
          onChange={(e) => setColors(e.target.value)}
          placeholder="trắng, đen, be"
        />
      </div>
      <div className="md:col-span-2 space-y-2">
        <Label>Tags (phân cách dấu phẩy)</Label>
        <Input
          value={tags}
          onChange={(e) => setTags(e.target.value)}
          placeholder="mùa hè, công sở, basic"
        />
      </div>

      <div className="md:col-span-2 flex justify-end gap-2 pt-2">
        {onCancel && (
          <Button variant="outline" onClick={onCancel} disabled={submitting}>
            Huỷ
          </Button>
        )}
        <Button onClick={handleSubmit} disabled={submitting}>
          {submitting ? "Đang lưu..." : submitLabel}
        </Button>
      </div>
    </div>
  );
}