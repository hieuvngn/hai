import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { CartView } from "@/types";

const CART_ID_KEY = "fashion-chatbot.cart_id";
const CART_TOKEN_KEY = "fashion-chatbot.cart_token";

function getCartId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(CART_ID_KEY);
}

function getCartToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(CART_TOKEN_KEY);
}

function setCart(id: string, token: string) {
  if (typeof window === "undefined") return;
  localStorage.setItem(CART_ID_KEY, id);
  localStorage.setItem(CART_TOKEN_KEY, token);
}

function clearCart() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(CART_ID_KEY);
  localStorage.removeItem(CART_TOKEN_KEY);
}

export function useCart() {
  const [cart, setCartState] = useState<CartView | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const id = getCartId();
    const token = getCartToken();
    if (!id || !token) {
      // No cart yet, create one
      setIsLoading(true);
      setError(null);
      try {
        const created = await api.createCart();
        setCart(created.cart_id, created.cart_token);
        const view = await api.getCart(created.cart_id, created.cart_token);
        setCartState(view);
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setIsLoading(false);
      }
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const view = await api.getCart(id, token);
      setCartState(view);
    } catch (e) {
      const msg = (e as Error).message;
      // If 401 or 404, cart invalid -> clear and recreate on next operation
      if (msg.includes("401") || msg.includes("404")) {
        clearCart();
        setCartState(null);
        try {
          const created = await api.createCart();
          setCart(created.cart_id, created.cart_token);
          const view2 = await api.getCart(created.cart_id, created.cart_token);
          setCartState(view2);
        } catch (e2) {
          setError((e2 as Error).message);
        }
      } else {
        setError(msg);
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    refresh();
  }, [refresh]);

  const ensureCart = useCallback(async (): Promise<{ id: string; token: string } | null> => {
    let id = getCartId();
    let token = getCartToken();
    if (id && token) return { id, token };
    try {
      const created = await api.createCart();
      setCart(created.cart_id, created.cart_token);
      return { id: created.cart_id, token: created.cart_token };
    } catch (e) {
      setError((e as Error).message);
      return null;
    }
  }, []);

  const addItem = useCallback(
    async (productId: string, size: string, quantity: number) => {
      setIsLoading(true);
      setError(null);
      try {
        const creds = await ensureCart();
        if (!creds) return;
        const view = await api.addCartItem(creds.id, creds.token, {
          product_id: productId,
          size,
          quantity,
        });
        setCartState(view);
      } catch (e) {
        const msg = (e as Error).message;
        if (msg.includes("401") || msg.includes("404")) {
          clearCart();
          const creds2 = await ensureCart();
          if (!creds2) return;
          try {
            const view2 = await api.addCartItem(creds2.id, creds2.token, {
              product_id: productId,
              size,
              quantity,
            });
            setCartState(view2);
          } catch (e2) {
            setError((e2 as Error).message);
          }
        } else {
          setError(msg);
        }
      } finally {
        setIsLoading(false);
      }
    },
    [ensureCart]
  );

  const updateQuantity = useCallback(
    async (productId: string, size: string, quantity: number) => {
      const id = getCartId();
      const token = getCartToken();
      if (!id || !token) return;
      setIsLoading(true);
      setError(null);
      try {
        const view = await api.updateCartItem(id, token, productId, size, quantity);
        setCartState(view);
      } catch (e) {
        const msg = (e as Error).message;
        if (msg.includes("401") || msg.includes("404")) {
          clearCart();
          await refresh();
        } else {
          setError(msg);
        }
      } finally {
        setIsLoading(false);
      }
    },
    [refresh]
  );

  const removeItem = useCallback(
    async (productId: string, size: string) => {
      const id = getCartId();
      const token = getCartToken();
      if (!id || !token) return;
      setIsLoading(true);
      setError(null);
      try {
        const view = await api.removeCartItem(id, token, productId, size);
        setCartState(view);
      } catch (e) {
        const msg = (e as Error).message;
        if (msg.includes("401") || msg.includes("404")) {
          clearCart();
          await refresh();
        } else {
          setError(msg);
        }
      } finally {
        setIsLoading(false);
      }
    },
    [refresh]
  );

  const cartId = typeof window !== "undefined" ? getCartId() : null;
  const cartToken = typeof window !== "undefined" ? getCartToken() : null;

  return {
    cart,
    cartId,
    cartToken,
    refresh,
    addItem,
    updateQuantity,
    removeItem,
    isLoading,
    error,
  };
}
