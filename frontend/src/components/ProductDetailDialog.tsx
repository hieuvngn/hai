import { useState, useEffect } from "react";
import type { Product } from "@/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { formatVnd } from "@/lib/utils";

interface Props {
  open: boolean;
  onOpenChange: (b: boolean) => void;
  product: Product | null;
  onAddToCart?: (product: Product, size: string, quantity: number) => void;
}

export function ProductDetailDialog({ open, onOpenChange, product, onAddToCart }: Props) {
  const [selectedSize, setSelectedSize] = useState<string>("");
  const [quantity, setQuantity] = useState<string>("1");
  const [imgError, setImgError] = useState(false);

  useEffect(() => {
    if (product) {
      const inStock = product.sizes_available.filter((s) => (product.stock_per_size[s] ?? 0) > 0);
      setSelectedSize(inStock[0] ?? "");
      setQuantity("1");
      setImgError(false);
    }
  }, [product]);

  // Reset imgError when product changes or dialog opens
  useEffect(() => {
    if (open) setImgError(false);
  }, [open, product?.id]);

  if (!product) return null;

  const totalStock = Object.values(product.stock_per_size).reduce((a, b) => a + b, 0);
  const hasImage = product.image_url && !imgError;
  const selectedStock = selectedSize ? (product.stock_per_size[selectedSize] ?? 0) : 0;
  const canAdd = !!selectedSize && selectedStock > 0 && !!onAddToCart;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-left">{product.name}</DialogTitle>
          <DialogDescription className="sr-only">{product.description}</DialogDescription>
        </DialogHeader>

        <div className="grid gap-6 md:grid-cols-2">
          {/* Left: image */}
          <div className="aspect-square w-full overflow-hidden rounded-md bg-muted">
            {hasImage ? (
              <img
                src={product.image_url}
                alt={product.name}
                className="h-full w-full object-cover"
                loading="lazy"
                onError={() => setImgError(true)}
              />
            ) : (
              <div className="flex h-full w-full items-center justify-center aspect-square bg-muted text-muted-foreground text-sm">
                Không có ảnh
              </div>
            )}
          </div>

          {/* Right: details */}
          <div className="flex flex-col gap-3">
            <p className="text-xs text-muted-foreground">{product.brand}</p>
            <h2 className="text-lg font-semibold leading-tight">{product.name}</h2>
            <div>
              <Badge variant="secondary">{product.category}</Badge>
            </div>
            <p className="text-lg font-bold text-primary">{formatVnd(product.price_vnd)}</p>

            <p className="text-sm text-muted-foreground max-h-40 overflow-y-auto">{product.description}</p>

            {/* Sizes */}
            <div className="space-y-1.5">
              <p className="text-xs font-medium">Kích cỡ</p>
              <div className="flex flex-wrap gap-1.5">
                {product.sizes_available.map((s) => {
                  const qty = product.stock_per_size[s] ?? 0;
                  const isSelected = s === selectedSize;
                  const isOut = qty === 0;
                  return (
                    <Button
                      key={s}
                      variant={isSelected ? "default" : "outline"}
                      size="sm"
                      className="h-7 px-2.5 text-xs"
                      disabled={isOut}
                      onClick={() => setSelectedSize(s)}
                    >
                      {s}
                      {isOut ? " · hết" : ""}
                    </Button>
                  );
                })}
              </div>
            </div>

            {/* Colors */}
            {product.colors.length > 0 && (
              <div className="space-y-1.5">
                <p className="text-xs font-medium">Màu sắc</p>
                <div className="flex flex-wrap gap-1">
                  {product.colors.map((c) => (
                    <Badge key={c} variant="outline" className="text-[11px]">
                      {c}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {/* Material */}
            <p className="text-xs">
              <span className="font-medium">Chất liệu:</span> <span className="text-muted-foreground">{product.material}</span>
            </p>

            {/* Tags */}
            {product.tags.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {product.tags.map((t) => (
                  <Badge key={t} variant="secondary" className="text-[11px] font-normal">
                    {t}
                  </Badge>
                ))}
              </div>
            )}

            <p className="text-xs text-muted-foreground">
              {totalStock > 0 ? `Còn ${totalStock} sản phẩm` : "Tạm hết hàng"} · Giới tính: {product.gender}
            </p>
          </div>
        </div>

        <DialogFooter className="flex flex-col sm:flex-row gap-2 sm:items-center">
          {onAddToCart && (
            <div className="flex items-center gap-2 mr-auto">
              <Select value={quantity} onValueChange={setQuantity}>
                <SelectTrigger className="h-9 w-[90px]">
                  <SelectValue placeholder="SL" />
                </SelectTrigger>
                <SelectContent>
                  {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
                    <SelectItem key={n} value={String(n)}>
                      {n}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                disabled={!canAdd}
                onClick={() => {
                  if (product && selectedSize) {
                    onAddToCart(product, selectedSize, Number(quantity) || 1);
                  }
                }}
              >
                Thêm vào giỏ
              </Button>
            </div>
          )}
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Đóng
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
