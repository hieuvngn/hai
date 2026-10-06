import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import type { CartView } from "@/types";
import type { CustomerProfile } from "@/hooks/use-customer-profile";
import { useCustomerProfile } from "@/hooks/use-customer-profile";
import { formatVnd } from "@/lib/utils";

interface Props {
  open: boolean;
  onOpenChange: (b: boolean) => void;
  cart: CartView | null;
  onPlaceOrder: (profile: CustomerProfile) => Promise<void>;
  isSubmitting: boolean;
}

export function CheckoutDialog({
  open,
  onOpenChange,
  cart,
  onPlaceOrder,
  isSubmitting,
}: Props) {
  const { profile } = useCustomerProfile();
  const [phone, setPhone] = useState("");
  const [name, setName] = useState("");
  const [address, setAddress] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open && profile) {
      setPhone(profile.phone ?? "");
      setName(profile.name ?? "");
      setAddress(profile.address ?? "");
    }
  }, [open, profile]);

  async function handleSubmit() {
    setError(null);
    if (!phone.trim()) {
      setError("Vui lòng nhập số điện thoại");
      return;
    }
    if (!name.trim()) {
      setError("Vui lòng nhập họ tên");
      return;
    }
    if (!address.trim()) {
      setError("Vui lòng nhập địa chỉ");
      return;
    }
    try {
      await onPlaceOrder({
        phone: phone.trim(),
        name: name.trim(),
        address: address.trim(),
      });
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Xác nhận đặt hàng</DialogTitle>
          <DialogDescription>
            Vui lòng kiểm tra thông tin giao hàng trước khi đặt
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {cart && (
            <div className="rounded-md bg-muted p-3 text-sm">
              <p className="font-medium">{cart.items.length} sản phẩm</p>
              <p className="font-bold text-primary">{formatVnd(cart.total_vnd)}</p>
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="checkout-phone">Số điện thoại *</Label>
            <Input
              id="checkout-phone"
              type="tel"
              placeholder="0912345678"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="checkout-name">Họ tên *</Label>
            <Input
              id="checkout-name"
              placeholder="Nguyễn Văn A"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="checkout-address">Địa chỉ *</Label>
            <Textarea
              id="checkout-address"
              placeholder="Số nhà, đường, quận/huyện, tỉnh/thành"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              rows={3}
            />
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}

          <Button
            className="w-full"
            onClick={handleSubmit}
            disabled={isSubmitting || !cart || cart.items.length === 0}
          >
            {isSubmitting ? "Đang đặt..." : "Xác nhận đặt"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
