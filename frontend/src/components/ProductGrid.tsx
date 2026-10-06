import { useCallback, useEffect, useState } from "react";
import type { Product } from "@/types";
import { api } from "@/lib/api";
import { ProductCard } from "@/components/ProductCard";
import { ProductDetailDialog } from "@/components/ProductDetailDialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Search, X } from "lucide-react";

interface Props {
  onAddToCart?: (product: Product, size: string, quantity: number) => void;
}

const CATEGORIES = ["Tất cả", "áo", "quần", "váy", "giày", "phụ kiện", "đồ thể thao"] as const;
const PAGE_LIMIT = 24;

export function ProductGrid({ onAddToCart }: Props) {
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [category, setCategory] = useState<string>("Tất cả");
  const [minPrice, setMinPrice] = useState<string>("");
  const [maxPrice, setMaxPrice] = useState<string>("");

  const [items, setItems] = useState<Product[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [offset, setOffset] = useState(0);
  const [hasInitialized, setHasInitialized] = useState(false);

  const [selected, setSelected] = useState<Product | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  const fetchProducts = useCallback(
    async (nextOffset: number, append: boolean) => {
      setLoading(true);
      try {
        const params: Record<string, string | number> = {
          limit: PAGE_LIMIT,
          offset: nextOffset,
        };
        if (category && category !== "Tất cả") params.category = category;
        if (search.trim() !== "") params.search = search.trim();
        if (minPrice.trim() !== "") {
          const v = Number(minPrice);
          if (!Number.isNaN(v) && v >= 0) params.min_price = v;
        }
        if (maxPrice.trim() !== "") {
          const v = Number(maxPrice);
          if (!Number.isNaN(v) && v >= 0) params.max_price = v;
        }
        const res = await api.listProducts(params);
        setTotal(res.total);
        if (append) {
          setItems((prev) => [...prev, ...res.items]);
        } else {
          setItems(res.items);
        }
        setOffset(nextOffset);
        setHasInitialized(true);
      } catch (e) {
        console.error("Failed to fetch products", e);
      } finally {
        setLoading(false);
      }
    },
    [category, search, minPrice, maxPrice]
  );

  // Fetch on filter change (reset pagination)
  useEffect(() => {
    fetchProducts(0, false);
  }, [fetchProducts]);

  const handleSearchSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setSearch(searchInput);
  };

  const handleClear = () => {
    setSearchInput("");
    setSearch("");
    setCategory("Tất cả");
    setMinPrice("");
    setMaxPrice("");
  };

  const handleLoadMore = () => {
    const next = offset + PAGE_LIMIT;
    fetchProducts(next, true);
  };

  const hasMore = items.length < total;

  const handleCardClick = (product: Product) => {
    setSelected(product);
    setDialogOpen(true);
  };

  return (
    <div className="w-full space-y-4">
      {/* Top bar: filters */}
      <form onSubmit={handleSearchSubmit} className="flex flex-col gap-3">
        <div className="flex flex-col sm:flex-row gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Tìm kiếm sản phẩm..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="pl-8"
            />
          </div>
          <Button type="submit" variant="secondary" className="shrink-0">
            Tìm
          </Button>
        </div>

        <div className="flex flex-col sm:flex-row gap-2">
          <Select value={category} onValueChange={setCategory}>
            <SelectTrigger className="w-full sm:w-[180px]">
              <SelectValue placeholder="Danh mục" />
            </SelectTrigger>
            <SelectContent>
              {CATEGORIES.map((c) => (
                <SelectItem key={c} value={c}>
                  {c === "Tất cả" ? "Tất cả danh mục" : c}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Input
            type="number"
            placeholder="Giá tối thiểu"
            value={minPrice}
            onChange={(e) => setMinPrice(e.target.value)}
            min={0}
            className="w-full sm:w-[160px]"
          />
          <Input
            type="number"
            placeholder="Giá tối đa"
            value={maxPrice}
            onChange={(e) => setMaxPrice(e.target.value)}
            min={0}
            className="w-full sm:w-[160px]"
          />
          <Button type="button" variant="outline" onClick={handleClear} className="shrink-0">
            <X className="mr-1 h-4 w-4" />
            Xóa lọc
          </Button>
        </div>
      </form>

      <p className="text-xs text-muted-foreground">
        {hasInitialized ? `${total} sản phẩm` : "Đang tải..."}
      </p>

      {/* Grid */}
      {items.length === 0 ? (
        hasInitialized && !loading ? (
          <div className="py-12 text-center text-sm text-muted-foreground">
            Không tìm thấy sản phẩm nào.
          </div>
        ) : loading ? (
          <div className="py-12 text-center text-sm text-muted-foreground">Đang tải sản phẩm...</div>
        ) : null
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {items.map((p) => (
            <div
              key={p.id}
              onClick={(e) => {
                // Prevent opening dialog when clicking inner buttons/selects (Thêm vào giỏ)
                const target = e.target as HTMLElement;
                if (target.closest("button")) return;
                handleCardClick(p);
              }}
              className="cursor-pointer"
            >
              <ProductCard product={p} onAdd={onAddToCart} />
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      <div className="flex justify-center pt-2">
        {loading && items.length > 0 && (
          <p className="text-sm text-muted-foreground">Đang tải...</p>
        )}
        {!loading && hasMore && items.length > 0 && (
          <Button variant="outline" onClick={handleLoadMore}>
            Xem thêm
          </Button>
        )}
      </div>

      <ProductDetailDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        product={selected}
        onAddToCart={onAddToCart}
      />
    </div>
  );
}
