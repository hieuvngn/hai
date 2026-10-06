export type Category =
  | "áo"
  | "quần"
  | "váy"
  | "giày"
  | "phụ kiện"
  | "đồ thể thao";

export type Gender = "nam" | "nữ" | "unisex";

export interface Product {
  id: string;
  name: string;
  brand: string;
  category: Category;
  description: string;
  price_vnd: number;
  sizes_available: string[];
  colors: string[];
  material: string;
  stock_per_size: Record<string, number>;
  tags: string[];
  image_url: string;
  gender: Gender;
  created_at?: string;
}

// ============ Chat ============

export interface ChatRequest {
  session_id: string;
  message: string;
  cart_id?: string | null;
  cart_token?: string | null;
}

export interface ToolCallRecord {
  tool: string;
  arguments: Record<string, unknown>;
  result_preview: string;
}

export interface ChatResponse {
  session_id: string;
  reply: string;
  tool_calls: ToolCallRecord[];
  products: Product[];
}

// ============ Cart ============

export interface CartItem {
  product_id: string;
  size: string;
  quantity: number;
  price_vnd_snapshot: number;
  name_snapshot: string;
  image_url_snapshot: string;
}

export interface Cart {
  cart_id: string;
  cart_token: string;
  items: CartItem[];
  created_at: string;
  last_seen_at: string;
}

export interface CartView {
  cart_id: string;
  items: CartItem[];
  created_at: string;
  last_seen_at: string;
  total_vnd: number;
}

export interface CartCreateResponse {
  cart_id: string;
  cart_token: string;
}

export interface AddToCartRequest {
  product_id: string;
  size: string;
  quantity: number;
}

// ============ Order ============

export type OrderStatus = "pending" | "confirmed" | "shipped" | "completed" | "cancelled" | "failed";

export interface OrderItem {
  product_id: string;
  size: string;
  quantity: number;
  price_vnd_snapshot: number;
  name_snapshot: string;
  image_url_snapshot: string;
}

export interface Order {
  order_id: string;
  customer_phone: string;
  customer_name: string;
  customer_address: string;
  items: OrderItem[];
  status: OrderStatus;
  created_at: string;
  status_history: Array<{ status: string; at: string }>;
  total_vnd: number;
}

export interface AdminOrderRow {
  order_id: string;
  customer_phone: string;
  customer_name: string;
  customer_address: string;
  items: OrderItem[];
  status: OrderStatus;
  created_at: string;
  total_vnd: number;
  price_mismatch: boolean;
}

export interface AdminOrdersResponse {
  orders: AdminOrderRow[];
  total: number;
  price_mismatch_count: number;
}

export interface OrderTransitionRequest {
  new_status: OrderStatus;
}

// ============ Admin ============

export interface AdminLoginRequest {
  token: string;
}

export interface AdminStats {
  total_products: number;
  active_sessions: number;
  total_customers: number;
  top_products: Array<{ id: string; name?: string; count: number }>;
  price_mismatch_count: number;
}

export interface AdminProductCreate {
  name: string;
  brand: string;
  category: Category;
  description: string;
  price_vnd: number;
  sizes_available: string[];
  colors: string[];
  material: string;
  stock_per_size: Record<string, number>;
  tags: string[];
  image_url?: string;
  gender: Gender;
}
export type AdminProductUpdate = Partial<AdminProductCreate>;

// ============ Product Browse ============
export interface ProductListResponse {
  total: number;
  items: Product[];
}
