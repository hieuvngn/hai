import { useState } from "react";
import type { Product } from "@/types";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { formatVnd } from "@/lib/utils";
import { ShoppingCart } from "lucide-react";

interface Props {
  product: Product;
  onAdd?: (product: Product, size: string, quantity: number) => void;
}

export function ProductCard({ product, onAdd }: Props) {
  const inStockSizes = product.sizes_available.filter(
    (s) => (product.stock_per_size[s] ?? 0) > 0
  );
  const totalStock = Object.values(product.stock_per_size).reduce(
    (a, b) => a + b,
    0
  );
  const [selectedSize, setSelectedSize] = useState<string>(
    inStockSizes[0] ?? product.sizes_available[0] ?? ""
  );

  return (
    <Card className="overflow-hidden">
      <div className="aspect-square w-full overflow-hidden bg-muted">
        <img
          src={product.image_url}
          alt={product.name}
          className="h-full w-full object-cover"
          loading="lazy"
          onError={(e) => {
            (e.currentTarget as HTMLImageElement).style.display = "none";
          }}
        />
      </div>
      <CardContent className="space-y-2 p-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="truncate text-xs text-muted-foreground">
              {product.brand}
            </p>
            <h4 className="line-clamp-2 text-sm font-semibold leading-tight">
              {product.name}
            </h4>
          </div>
          <Badge variant="secondary" className="shrink-0">
            {product.category}
          </Badge>
        </div>

        <p className="text-sm font-bold text-primary">
          {formatVnd(product.price_vnd)}
        </p>

        <div className="flex flex-wrap gap-1">
          {product.sizes_available.map((s) => {
            const qty = product.stock_per_size[s] ?? 0;
            return (
              <Badge
                key={s}
                variant={qty > 0 ? "outline" : "destructive"}
                className="px-1.5 py-0 text-[10px]"
              >
                {s}
                {qty > 0 ? "" : " · hết"}
              </Badge>
            );
          })}
        </div>

        <p className="text-xs text-muted-foreground">
          {totalStock > 0
            ? `Còn ${totalStock} sản phẩm (${inStockSizes.length} size)`
            : "Tạm hết hàng"}
        </p>

        {onAdd && (
          <div className="flex items-center gap-2 pt-1">
            <Select value={selectedSize} onValueChange={setSelectedSize}>
              <SelectTrigger className="h-8 flex-1 text-xs">
                <SelectValue placeholder="Chọn size" />
              </SelectTrigger>
              <SelectContent>
                {product.sizes_available.map((s) => {
                  const qty = product.stock_per_size[s] ?? 0;
                  return (
                    <SelectItem key={s} value={s} disabled={qty <= 0}>
                      {s} {qty <= 0 ? "(hết)" : ""}
                    </SelectItem>
                  );
                })}
              </SelectContent>
            </Select>
            <Button
              size="sm"
              className="h-8 shrink-0 text-xs"
              disabled={inStockSizes.length === 0 || !selectedSize}
              onClick={() => {
                if (selectedSize) onAdd(product, selectedSize, 1);
              }}
            >
              <ShoppingCart className="mr-1 h-3.5 w-3.5" />
              Thêm vào giỏ
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
