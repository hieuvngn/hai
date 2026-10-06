import type {
  ChatRequest,
  ChatResponse,
  Product,
  ProductListResponse,
  AdminStats,
  AdminProductCreate,
  AdminProductUpdate,
  CartCreateResponse,
  CartView,
  AddToCartRequest,
  Order,
  AdminOrdersResponse,
  OrderStatus,
} from "@/types";

const API_BASE = ""; // proxy qua vite dev → http://localhost:8000

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { ...(init?.headers as Record<string, string> | undefined) };
  if (init?.body !== undefined && init.body !== null && !headers["Content-Type"] && !headers["content-type"]) {
    headers["Content-Type"] = "application/json";
  }
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const data = await res.json();
      msg = data.detail || data.message || msg;
    } catch {}
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

// ============ Public ============

export const api = {
  health: () => http<{ ok: boolean }>("/api/health"),

  chat: (req: ChatRequest) =>
    http<ChatResponse>("/api/chat", { method: "POST", body: JSON.stringify(req) }),
  getProduct: (id: string) => http<Product>(`/api/products/${id}`),

  listProducts: (params: {
    category?: string;
    search?: string;
    min_price?: number;
    max_price?: number;
    limit?: number;
    offset?: number;
  } = {}) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") qs.append(k, String(v));
    });
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return http<ProductListResponse>(`/api/products${suffix}`);
  },

  createCart: () => http<CartCreateResponse>("/api/cart", { method: "POST" }),

  getCart: (cartId: string, token: string) =>
    http<CartView>(`/api/cart/${cartId}`, { headers: { "X-Cart-Token": token } }),

  addCartItem: (cartId: string, token: string, body: AddToCartRequest) =>
    http<CartView>(`/api/cart/${cartId}/items`, {
      method: "POST",
      headers: { "X-Cart-Token": token },
      body: JSON.stringify(body),
    }),

  updateCartItem: (
    cartId: string,
    token: string,
    productId: string,
    size: string,
    quantity: number
  ) =>
    http<CartView>(`/api/cart/${cartId}/items/${productId}/${encodeURIComponent(size)}`, {
      method: "PUT",
      headers: { "X-Cart-Token": token },
      body: JSON.stringify({ quantity }),
    }),

  removeCartItem: (cartId: string, token: string, productId: string, size: string) =>
    http<CartView>(`/api/cart/${cartId}/items/${productId}/${encodeURIComponent(size)}`, {
      method: "DELETE",
      headers: { "X-Cart-Token": token },
    }),

  listMyOrders: (phone: string) =>
    http<Order[]>(`/api/orders/me?phone=${encodeURIComponent(phone)}`),
};

// ============ Admin ============

export const adminApi = {
  login: (token: string) =>
    http<{ ok: boolean }>("/api/admin/login", {
      method: "POST",
      body: JSON.stringify({ token }),
    }),

  logout: () =>
    http<{ ok: boolean }>("/api/admin/logout", { method: "POST" }),

  stats: (adminToken: string) =>
    http<AdminStats>("/api/admin/stats", {
      headers: { Authorization: `Bearer ${adminToken}` },
    }),

  listProducts: (adminToken: string) =>
    http<Product[]>("/api/admin/products", {
      headers: { Authorization: `Bearer ${adminToken}` },
    }),

  createProduct: (adminToken: string, body: AdminProductCreate) =>
    http<Product>("/api/admin/products", {
      method: "POST",
      headers: { Authorization: `Bearer ${adminToken}` },
      body: JSON.stringify(body),
    }),

  updateProduct: (
    adminToken: string,
    id: string,
    body: AdminProductUpdate
  ) =>
    http<Product>(`/api/admin/products/${id}`, {
      method: "PUT",
      headers: { Authorization: `Bearer ${adminToken}` },
      body: JSON.stringify(body),
    }),

  deleteProduct: (adminToken: string, id: string) =>
    http<{ ok: boolean; deleted: string }>(`/api/admin/products/${id}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${adminToken}` },
    }),

  rebuildIndex: (adminToken: string) =>
    http<{ ok: boolean; message: string }>("/api/admin/rebuild-index", {
      method: "POST",
      headers: { Authorization: `Bearer ${adminToken}` },
    }),

  listOrders: (adminToken: string, priceMismatchOnly = false) =>
    http<AdminOrdersResponse>(
      "/api/admin/orders" + (priceMismatchOnly ? "?price_mismatch_only=true" : ""),
      {
        headers: { Authorization: `Bearer ${adminToken}` },
      }
    ),

  transitionOrder: (adminToken: string, orderId: string, newStatus: OrderStatus) =>
    http<Order>(`/api/admin/orders/${orderId}/transition`, {
      method: "POST",
      headers: { Authorization: `Bearer ${adminToken}` },
      body: JSON.stringify({ new_status: newStatus }),
    }),
};
