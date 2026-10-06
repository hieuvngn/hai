import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useCart } from "@/hooks/use-cart";

const CART_ID_KEY = "fashion-chatbot.cart_id";
const CART_TOKEN_KEY = "fashion-chatbot.cart_token";

// Mock api module — hook chỉ tương tác qua api.*
vi.mock("@/lib/api", () => ({
  api: {
    createCart: vi.fn(),
    getCart: vi.fn(),
    addCartItem: vi.fn(),
    updateCartItem: vi.fn(),
    removeCartItem: vi.fn(),
  },
}));

import { api } from "@/lib/api";

const cartView = (items: unknown[] = []) => ({
  cart_id: "cid-1",
  items,
  created_at: new Date().toISOString(),
  last_seen_at: new Date().toISOString(),
  total_vnd: 0,
});

describe("useCart", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it("tự tạo cart khi chưa có trong localStorage", async () => {
    vi.mocked(api.createCart).mockResolvedValue({ cart_id: "cid-1", cart_token: "tok-1" });
    vi.mocked(api.getCart).mockResolvedValue(cartView() as never);

    const { result } = renderHook(() => useCart());
    await waitFor(() => expect(result.current.cart).not.toBeNull());

    expect(api.createCart).toHaveBeenCalledTimes(1);
    expect(localStorage.getItem(CART_ID_KEY)).toBe("cid-1");
    expect(localStorage.getItem(CART_TOKEN_KEY)).toBe("tok-1");
    expect(api.getCart).toHaveBeenCalledWith("cid-1", "tok-1");
  });

  it("dùng lại cart đã lưu — không createCart", async () => {
    localStorage.setItem(CART_ID_KEY, "old-id");
    localStorage.setItem(CART_TOKEN_KEY, "old-token");
    vi.mocked(api.getCart).mockResolvedValue(cartView() as never);

    renderHook(() => useCart());
    await waitFor(() => expect(api.getCart).toHaveBeenCalled());
    expect(api.createCart).not.toHaveBeenCalled();
  });

  it("cart token hết hạn (401) → clear + tự tạo cart mới", async () => {
    localStorage.setItem(CART_ID_KEY, "stale");
    localStorage.setItem(CART_TOKEN_KEY, "bad");
    vi.mocked(api.getCart)
      .mockRejectedValueOnce(new Error("HTTP 401"))
      .mockResolvedValueOnce(cartView() as never);
    vi.mocked(api.createCart).mockResolvedValue({ cart_id: "fresh", cart_token: "fresh-tok" });

    const { result } = renderHook(() => useCart());
    await waitFor(() => expect(api.createCart).toHaveBeenCalledTimes(1));
    expect(localStorage.getItem(CART_ID_KEY)).toBe("fresh");
    expect(result.current.error).toBeNull();
  });

  it("addItem gọi đúng api với product/size/qty", async () => {
    localStorage.setItem(CART_ID_KEY, "cid-1");
    localStorage.setItem(CART_TOKEN_KEY, "tok-1");
    vi.mocked(api.getCart).mockResolvedValue(cartView() as never);
    vi.mocked(api.addCartItem).mockResolvedValue(
      cartView([{ product_id: "P001", size: "M", quantity: 2 }]) as never
    );

    const { result } = renderHook(() => useCart());
    await waitFor(() => expect(result.current.cart).not.toBeNull());

    await act(async () => {
      await result.current.addItem("P001", "M", 2);
    });
    expect(api.addCartItem).toHaveBeenCalledWith("cid-1", "tok-1", {
      product_id: "P001",
      size: "M",
      quantity: 2,
    });
    expect(result.current.cart?.items).toHaveLength(1);
  });
});
