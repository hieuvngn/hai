import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ChatWindow } from "@/components/ChatWindow";
import { CartDrawer } from "@/components/CartDrawer";
import { CheckoutDialog } from "@/components/CheckoutDialog";
import { ProductGrid } from "@/components/ProductGrid";
import { ProductDetailDialog } from "@/components/ProductDetailDialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useCart } from "@/hooks/use-cart";
import { useCustomerProfile } from "@/hooks/use-customer-profile";
import type { CustomerProfile } from "@/hooks/use-customer-profile";
import { api } from "@/lib/api";
import { useSession } from "@/hooks/use-session";
import { ShoppingCart } from "lucide-react";
import type { Product } from "@/types";

interface Props {
  initialProductId?: string;
}

export function ChatPage({ initialProductId }: Props) {
  const params = useParams<{ id: string }>();
  const resolvedInitialId = initialProductId ?? params.id;
  const { sessionId } = useSession();
  const { cart, cartId, cartToken, refresh, addItem, updateQuantity, removeItem, isLoading } =
    useCart();
  const { save: saveProfile } = useCustomerProfile();
  const [cartOpen, setCartOpen] = useState(false);
  const [checkoutOpen, setCheckoutOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [initialProduct, setInitialProduct] = useState<Product | null>(null);
  const [initialDialogOpen, setInitialDialogOpen] = useState(false);

  useEffect(() => {
    if (!resolvedInitialId) return;
    let cancelled = false;
    api
      .getProduct(resolvedInitialId)
      .then((p) => {
        if (!cancelled) {
          setInitialProduct(p);
          setInitialDialogOpen(true);
        }
      })
      .catch(() => {
        // ignore fetch errors (404 etc.)
      });
    return () => {
      cancelled = true;
    };
  }, [resolvedInitialId]);

  async function handleAdd(product: Product, size: string, quantity: number) {
    await addItem(product.id, size, quantity);
  }

  async function handlePlaceOrder(profile: CustomerProfile) {
    saveProfile(profile);
    setIsSubmitting(true);
    try {
      const text = `Tôi muốn đặt đơn. Số điện thoại ${profile.phone}, tên ${profile.name}, địa chỉ ${profile.address}.`;
      await api.chat({
        session_id: sessionId,
        message: text,
        cart_id: cartId,
        cart_token: cartToken,
      });
      setCheckoutOpen(false);
      setCartOpen(false);
      await refresh();
      setToast("Đặt hàng thành công! Kiểm tra tin nhắn để xem chi tiết đơn.");
      setTimeout(() => setToast(null), 4000);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center bg-muted/30 p-4">
      <div className="w-full max-w-3xl flex items-center justify-between pb-2">
        <Link to="/admin">
          <Button variant="link" size="sm">
            → Trang quản trị
          </Button>
        </Link>
        <Button variant="outline" onClick={() => setCartOpen(true)}>
          <ShoppingCart className="mr-2 h-4 w-4" />
          Giỏ hàng
          {cart && cart.items.length > 0 && (
            <Badge className="ml-2">{cart.items.length}</Badge>
          )}
        </Button>
      </div>

      {toast && (
        <div className="w-full max-w-3xl pb-2">
          <p className="rounded-md bg-green-100 px-4 py-2 text-sm text-green-800">
            {toast}
          </p>
        </div>
      )}

      <Tabs defaultValue="chat" className="w-full max-w-3xl">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="chat">Chat</TabsTrigger>
          <TabsTrigger value="products">Sản phẩm</TabsTrigger>
        </TabsList>
        <TabsContent value="chat">
          <ChatWindow cart={cart} cartToken={cartToken} onAddToCart={handleAdd} />
        </TabsContent>
        <TabsContent value="products">
          <ProductGrid onAddToCart={handleAdd} />
        </TabsContent>
      </Tabs>

      <CartDrawer
        open={cartOpen}
        onOpenChange={setCartOpen}
        cart={cart}
        loading={isLoading}
        onUpdateQty={updateQuantity}
        onRemove={removeItem}
        onCheckout={() => {
          setCartOpen(false);
          setCheckoutOpen(true);
        }}
      />

      <CheckoutDialog
        open={checkoutOpen}
        onOpenChange={setCheckoutOpen}
        cart={cart}
        onPlaceOrder={handlePlaceOrder}
        isSubmitting={isSubmitting}
      />

      {resolvedInitialId && initialProduct && (
        <ProductDetailDialog
          open={initialDialogOpen}
          onOpenChange={setInitialDialogOpen}
          product={initialProduct}
          onAddToCart={handleAdd}
        />
      )}

      <p className="mt-2 text-xs text-muted-foreground">
        Chatbot có thể trả lời sai. Vui lòng xác nhận giá và tồn kho trước khi mua.
      </p>
    </div>
  );
}
