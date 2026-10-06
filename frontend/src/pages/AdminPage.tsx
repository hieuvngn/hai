import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ProductForm } from "@/components/ProductForm";
import { adminApi } from "@/lib/api";
import { useAdminToken } from "@/hooks/use-session";
import type {
  AdminProductCreate,
  AdminProductUpdate,
  AdminStats,
  AdminOrderRow,
  OrderStatus,
  Product,
} from "@/types";
import { formatVnd } from "@/lib/utils";

type Tab = "dashboard" | "products" | "orders";
type FormPayload = AdminProductCreate | AdminProductUpdate;

const STATUS_TRANSITIONS: Record<OrderStatus, OrderStatus[]> = {
  pending: ["confirmed", "cancelled"],
  confirmed: ["shipped", "cancelled"],
  shipped: ["completed", "failed"],
  completed: [],
  cancelled: [],
  failed: [],
};

function statusBadgeVariant(status: OrderStatus): "default" | "secondary" | "outline" | "destructive" {
  switch (status) {
    case "pending":
      return "outline";
    case "confirmed":
      return "secondary";
    case "shipped":
      return "default";
    case "completed":
      return "default";
    case "cancelled":
    case "failed":
      return "destructive";
    default:
      return "outline";
  }
}

export function AdminPage() {
  const { token, save, clear } = useAdminToken();
  const [loginInput, setLoginInput] = useState("");
  const [loginError, setLoginError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("dashboard");

  async function handleLogin() {
    setLoginError(null);
    try {
      await adminApi.login(loginInput);
      save(loginInput);
    } catch (e) {
      setLoginError((e as Error).message);
    }
  }

  if (!token) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-muted/30 p-4">
        <Card className="w-full max-w-sm">
          <CardHeader>
            <CardTitle>Đăng nhập quản trị</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-2">
              <Label>Admin token</Label>
              <Input
                type="password"
                value={loginInput}
                onChange={(e) => setLoginInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleLogin();
                }}
              />
            </div>
            {loginError && (
              <p className="text-sm text-destructive">{loginError}</p>
            )}
            <Button onClick={handleLogin} className="w-full">
              Đăng nhập
            </Button>
            <Link
              to="/"
              className="block text-center text-xs text-muted-foreground hover:underline"
            >
              ← Về trang chat
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-muted/30">
      <header className="border-b bg-background">
        <div className="container flex items-center justify-between py-3">
          <div className="flex items-center gap-4">
            <h1 className="text-lg font-semibold">Quản trị</h1>
            <nav className="flex gap-2">
              <Button
                variant={tab === "dashboard" ? "default" : "ghost"}
                size="sm"
                onClick={() => setTab("dashboard")}
              >
                Dashboard
              </Button>
              <Button
                variant={tab === "products" ? "default" : "ghost"}
                size="sm"
                onClick={() => setTab("products")}
              >
                Sản phẩm
              </Button>
              <Button
                variant={tab === "orders" ? "default" : "ghost"}
                size="sm"
                onClick={() => setTab("orders")}
              >
                Đơn hàng
              </Button>
            </nav>
          </div>
          <div className="flex items-center gap-2">
            <Link to="/">
              <Button variant="link" size="sm">
                Trang chat
              </Button>
            </Link>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                adminApi.logout().catch(() => {});
                clear();
              }}
            >
              Đăng xuất
            </Button>
          </div>
        </div>
      </header>

      <main className="container py-6">
        {tab === "dashboard" ? (
          <DashboardView token={token} />
        ) : tab === "products" ? (
          <ProductsView token={token} />
        ) : (
          <OrdersView token={token} />
        )}
      </main>
    </div>
  );
}

function DashboardView({ token }: { token: string }) {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [rebuilding, setRebuilding] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function refresh() {
    try {
      setStats(await adminApi.stats(token));
    } catch (e) {
      setMsg(`Lỗi: ${(e as Error).message}`);
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function rebuild() {
    setRebuilding(true);
    setMsg(null);
    try {
      const r = await adminApi.rebuildIndex(token);
      setMsg(r.message);
    } catch (e) {
      setMsg(`Lỗi: ${(e as Error).message}`);
    } finally {
      setRebuilding(false);
    }
  }

  if (!stats) return <p className="text-sm text-muted-foreground">Đang tải...</p>;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
        <StatCard label="Tổng sản phẩm" value={stats.total_products} />
        <StatCard label="Phiên đang hoạt động" value={stats.active_sessions} />
        <StatCard label="Tổng khách đã thấy" value={stats.total_customers} />
        <StatCard label="Đơn giá chênh" value={stats.price_mismatch_count} />
        <StatCard label="Top tư vấn" value={stats.top_products.length} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Top sản phẩm được tư vấn nhiều nhất</CardTitle>
        </CardHeader>
        <CardContent>
          {stats.top_products.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Chưa có dữ liệu. Khách phải chat trước.
            </p>
          ) : (
            <ul className="space-y-2">
              {stats.top_products.map((tp) => (
                <li
                  key={tp.id}
                  className="flex items-center justify-between border-b pb-2 last:border-b-0"
                >
                  <span className="text-sm">
                    <span className="font-mono text-xs text-muted-foreground">
                      {tp.id}
                    </span>{" "}
                    {tp.name ?? "(đã xoá)"}
                  </span>
                  <Badge>{tp.count} lượt</Badge>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Quản lý index</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Sau khi CRUD sản phẩm, bấm nút bên dưới để tính lại embeddings cho RAG.
          </p>
          <div className="flex items-center gap-2">
            <Button onClick={rebuild} disabled={rebuilding}>
              {rebuilding ? "Đang chạy..." : "Rebuild index"}
            </Button>
            <Button variant="outline" onClick={refresh}>
              Làm mới thống kê
            </Button>
          </div>
          {msg && <p className="text-xs text-muted-foreground">{msg}</p>}
        </CardContent>
      </Card>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <Card>
      <CardContent className="pt-6">
        <p className="text-sm text-muted-foreground">{label}</p>
        <p className="text-3xl font-bold">{value}</p>
      </CardContent>
    </Card>
  );
}

function OrdersView({ token }: { token: string }) {
  const [orders, setOrders] = useState<AdminOrderRow[]>([]);
  const [total, setTotal] = useState(0);
  const [priceMismatchCount, setPriceMismatchCount] = useState(0);
  const [priceMismatchOnly, setPriceMismatchOnly] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  async function fetchOrders(filter: boolean) {
    setLoading(true);
    setError(null);
    try {
      const res = await adminApi.listOrders(token, filter);
      setOrders(res.orders);
      setTotal(res.total);
      setPriceMismatchCount(res.price_mismatch_count);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchOrders(priceMismatchOnly);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [priceMismatchOnly]);

  async function handleTransition(orderId: string, newStatus: OrderStatus) {
    setActionError(null);
    try {
      await adminApi.transitionOrder(token, orderId, newStatus);
      await fetchOrders(priceMismatchOnly);
    } catch (e) {
      setActionError((e as Error).message);
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>
            Đơn hàng ({total}) {priceMismatchCount > 0 && `- ${priceMismatchCount} giá chênh`}
          </CardTitle>
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={priceMismatchOnly}
                onChange={(e) => setPriceMismatchOnly(e.target.checked)}
                className="h-4 w-4"
              />
              Chỉ đơn có giá chênh
            </label>
            <Button variant="outline" size="sm" onClick={() => fetchOrders(priceMismatchOnly)}>
              Làm mới
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {error && <p className="mb-2 text-sm text-destructive">{error}</p>}
          {actionError && <p className="mb-2 text-sm text-destructive">{actionError}</p>}
          {loading ? (
            <p className="text-sm text-muted-foreground">Đang tải...</p>
          ) : orders.length === 0 ? (
            <p className="text-sm text-muted-foreground">Không có đơn hàng</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left">
                    <th className="p-2">Mã đơn</th>
                    <th className="p-2">Khách hàng</th>
                    <th className="p-2">SL</th>
                    <th className="p-2">Tổng</th>
                    <th className="p-2">Trạng thái</th>
                    <th className="p-2">Giá chênh</th>
                    <th className="p-2">Ngày tạo</th>
                    <th className="p-2 text-right">Hành động</th>
                  </tr>
                </thead>
                <tbody>
                  {orders.map((o) => {
                    const nextStatuses = STATUS_TRANSITIONS[o.status] ?? [];
                    return (
                      <tr key={o.order_id} className="border-b hover:bg-muted/40">
                        <td className="p-2 font-mono text-xs">{o.order_id.slice(0, 8)}</td>
                        <td className="p-2">
                          <div className="font-medium">{o.customer_name}</div>
                          <div className="text-xs text-muted-foreground">{o.customer_phone}</div>
                          <div className="max-w-[200px] truncate text-xs text-muted-foreground">
                            {o.customer_address}
                          </div>
                        </td>
                        <td className="p-2">{o.items.length}</td>
                        <td className="p-2">{formatVnd(o.total_vnd)}</td>
                        <td className="p-2">
                          <Badge variant={statusBadgeVariant(o.status)}>{o.status}</Badge>
                        </td>
                        <td className="p-2">
                          {o.price_mismatch ? (
                            <Badge variant="destructive">chênh</Badge>
                          ) : (
                            <Badge variant="outline">ok</Badge>
                          )}
                        </td>
                        <td className="p-2 text-xs text-muted-foreground">
                          {new Date(o.created_at).toLocaleString("vi-VN")}
                        </td>
                        <td className="p-2 text-right">
                          {nextStatuses.length > 0 ? (
                            <Select
                              onValueChange={(v) => handleTransition(o.order_id, v as OrderStatus)}
                            >
                              <SelectTrigger className="h-8 w-[140px] text-xs">
                                <SelectValue placeholder="Chuyển trạng thái" />
                              </SelectTrigger>
                              <SelectContent>
                                {nextStatuses.map((s) => (
                                  <SelectItem key={s} value={s}>
                                    → {s}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          ) : (
                            <span className="text-xs text-muted-foreground">—</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function ProductsView({ token }: { token: string }) {
  const [products, setProducts] = useState<Product[]>([]);
  const [editing, setEditing] = useState<Product | null>(null);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      setProducts(await adminApi.listProducts(token));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleCreate(data: FormPayload) {
    try {
      await adminApi.createProduct(token, data as AdminProductCreate);
      setCreating(false);
      refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handleUpdate(data: FormPayload) {
    if (!editing) return;
    try {
      await adminApi.updateProduct(token, editing.id, data);
      setEditing(null);
      refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handleDelete(p: Product) {
    if (!confirm(`Xoá "${p.name}"?`)) return;
    try {
      await adminApi.deleteProduct(token, p.id);
      refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  if (creating || editing) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>
            {creating ? "Thêm sản phẩm" : `Sửa sản phẩm: ${editing?.id}`}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {error && <p className="mb-2 text-sm text-destructive">{error}</p>}
          <ProductForm
            initial={editing ?? undefined}
            submitLabel={creating ? "Tạo" : "Cập nhật"}
            onSubmit={creating ? handleCreate : handleUpdate}
            onCancel={() => {
              setCreating(false);
              setEditing(null);
              setError(null);
            }}
          />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Sản phẩm ({products.length})</CardTitle>
        <Button onClick={() => setCreating(true)}>+ Thêm</Button>
      </CardHeader>
      <CardContent>
        {error && <p className="mb-2 text-sm text-destructive">{error}</p>}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left">
                <th className="p-2">ID</th>
                <th className="p-2">Tên</th>
                <th className="p-2">Danh mục</th>
                <th className="p-2">Giá</th>
                <th className="p-2">Tồn</th>
                <th className="p-2 text-right">Hành động</th>
              </tr>
            </thead>
            <tbody>
              {products.map((p) => {
                const total = Object.values(p.stock_per_size).reduce(
                  (a, b) => a + b,
                  0
                );
                return (
                  <tr key={p.id} className="border-b hover:bg-muted/40">
                    <td className="p-2 font-mono text-xs">{p.id}</td>
                    <td className="p-2">
                      <div className="font-medium">{p.name}</div>
                      <div className="text-xs text-muted-foreground">
                        {p.brand}
                      </div>
                    </td>
                    <td className="p-2">{p.category}</td>
                    <td className="p-2">{formatVnd(p.price_vnd)}</td>
                    <td className="p-2">{total}</td>
                    <td className="p-2 text-right">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setEditing(p)}
                      >
                        Sửa
                      </Button>{" "}
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => handleDelete(p)}
                      >
                        Xoá
                      </Button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
