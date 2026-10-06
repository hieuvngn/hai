import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import type { CartView } from "@/types";
import { formatVnd } from "@/lib/utils";
import { Minus, Plus, Trash2 } from "lucide-react";

interface Props {
  open: boolean;
  onOpenChange: (b: boolean) => void;
  cart: CartView | null;
  loading: boolean;
  onUpdateQty: (productId: string, size: string, quantity: number) => void;
  onRemove: (productId: string, size: string) => void;
  onCheckout: () => void;
}

export function CartDrawer({
  open,
  onOpenChange,
  cart,
  loading,
  onUpdateQty,
  onRemove,
  onCheckout,
}: Props) {
  const isEmpty = !cart || cart.items.length === 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Giỏ hàng</DialogTitle>
          <DialogDescription>
            {cart ? `${cart.items.length} sản phẩm` : "Đang tải..."}
          </DialogDescription>
        </DialogHeader>

        {loading && !cart ? (
          <div className="space-y-3 py-4">
            <div className="h-16 animate-pulse rounded-md bg-muted" />
            <div className="h-16 animate-pulse rounded-md bg-muted" />
          </div>
        ) : isEmpty ? (
          <div className="py-8 text-center">
            <p className="text-sm text-muted-foreground">Giỏ hàng trống</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Thêm sản phẩm từ khung chat để bắt đầu mua sắm
            </p>
          </div>
        ) : (
          <>
            <div className="max-h-[50vh] space-y-3 overflow-y-auto pr-1">
              {cart!.items.map((item) => (
                <div
                  key={`${item.product_id}-${item.size}`}
                  className="flex items-center gap-3 rounded-md border p-2"
                >
                  <img
                    src={item.image_url_snapshot}
                    alt={item.name_snapshot}
                    className="h-10 w-10 shrink-0 rounded object-cover bg-muted"
                    onError={(e) => {
                      (e.currentTarget as HTMLImageElement).style.display = "none";
                    }}
                  />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{item.name_snapshot}</p>
                    <div className="flex items-center gap-1">
                      <Badge variant="outline" className="px-1.5 py-0 text-[10px]">
                        {item.size}
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        {formatVnd(item.price_vnd_snapshot)} × {item.quantity}
                      </span>
                    </div>
                    <p className="text-xs font-semibold text-primary">
                      {formatVnd(item.price_vnd_snapshot * item.quantity)}
                    </p>
                  </div>
                  <div className="flex items-center gap-1">
                    <Button
                      variant="outline"
                      size="icon"
                      className="h-7 w-7"
                      onClick={() => {
                        if (item.quantity > 1) {
                          onUpdateQty(item.product_id, item.size, item.quantity - 1);
                        }
                      }}
                      disabled={item.quantity <= 1}
                    >
                      <Minus className="h-3 w-3" />
                    </Button>
                    <span className="w-6 text-center text-sm">{item.quantity}</span>
                    <Button
                      variant="outline"
                      size="icon"
                      className="h-7 w-7"
                      onClick={() => onUpdateQty(item.product_id, item.size, item.quantity + 1)}
                    >
                      <Plus className="h-3 w-3" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 text-destructive hover:text-destructive"
                      onClick={() => onRemove(item.product_id, item.size)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>

            <div className="flex items-center justify-between border-t pt-4">
              <span className="text-sm font-medium">Tổng cộng</span>
              <span className="text-base font-bold text-primary">
                {formatVnd(cart!.total_vnd)}
              </span>
            </div>

            <Button className="w-full" onClick={onCheckout} disabled={isEmpty}>
              Đặt hàng
            </Button>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
