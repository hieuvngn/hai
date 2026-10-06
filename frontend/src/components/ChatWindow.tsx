import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ProductCard } from "@/components/ProductCard";
import { ProductDetailDialog } from "@/components/ProductDetailDialog";
import { api } from "@/lib/api";
import { useSession } from "@/hooks/use-session";
import type { CartView, ChatResponse, Product } from "@/types";
import { Eye } from "lucide-react";
import { Badge } from "@/components/ui/badge";

interface Message {
  role: "user" | "assistant";
  content: string;
  products?: Product[];
  toolCalls?: ChatResponse["tool_calls"];
}

interface ChatWindowProps {
  cart?: CartView | null;
  cartToken?: string | null;
  onAdd?: (product: Product, size: string, quantity: number) => void;
  onAddToCart?: (product: Product, size: string, quantity: number) => void;
}

export function ChatWindow({ cart, cartToken, onAdd, onAddToCart }: ChatWindowProps) {
  const handleAdd = onAdd ?? onAddToCart;
  const { sessionId, reset } = useSession();
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        "Xin chào! Mình là trợ lý tư vấn thời trang. Anh/chị đang tìm sản phẩm gì — áo, quần, váy, giày, phụ kiện hay đồ thể thao ạ?",
    },
  ]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [selected, setSelected] = useState<Product | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);

  async function openProductDetail(product: Product) {
    setDetailOpen(true);
    setSelected(product);
    setDetailLoading(true);
    try {
      const full = await api.getProduct(product.id);
      setSelected(full);
    } catch (err) {
      console.error("Không tải được chi tiết sản phẩm", err);
    } finally {
      setDetailLoading(false);
    }
  }

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, pending]);

  async function send() {
    const text = input.trim();
    if (!text || pending) return;
    const userMsg: Message = { role: "user", content: text };
    setMessages((m) => [...m, userMsg]);
    setInput("");
    setPending(true);
    try {
      const resp = await api.chat({
        session_id: sessionId,
        message: text,
        cart_id: cart?.cart_id ?? null,
        cart_token: cartToken ?? null,
      });
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: resp.reply,
          products: resp.products,
          toolCalls: resp.tool_calls,
        },
      ]);
    } catch (e) {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: `❌ Lỗi: ${(e as Error).message}`,
        },
      ]);
    } finally {
      setPending(false);
    }
  }

  return (
    <Card className="flex h-[80vh] w-full max-w-3xl flex-col">
      <CardHeader className="border-b">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">Tư vấn thời trang</CardTitle>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span>Phiên: {sessionId.slice(0, 8)}</span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                reset();
                setMessages([
                  {
                    role: "assistant",
                    content: "Đã bắt đầu phiên mới. Anh/chị cần tư vấn gì ạ?",
                  },
                ]);
              }}
            >
              Phiên mới
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent
        ref={scrollRef}
        className="flex-1 space-y-4 overflow-y-auto p-4"
      >
        {messages.map((m, i) => (
          <MessageBubble
            key={i}
            message={m}
            onAddToCart={handleAdd}
            onViewDetail={openProductDetail}
          />
        ))}
        {pending && (
          <div className="flex justify-start">
            <div className="rounded-lg bg-muted px-3 py-2 text-sm text-muted-foreground">
              Đang suy nghĩ...
            </div>
          </div>
        )}
      </CardContent>

      <div className="flex gap-2 border-t p-3">
        <Input
          placeholder="Nhập câu hỏi... (vd: 'tìm váy công sở size M dưới 1 triệu')"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          disabled={pending}
        />
        <Button onClick={send} disabled={pending || !input.trim()}>
          Gửi
        </Button>
      </div>
      <ProductDetailDialog
        open={detailOpen}
        onOpenChange={setDetailOpen}
        product={selected}
        onAddToCart={handleAdd}
      />
      {detailLoading && (
        <span className="sr-only">Đang tải chi tiết sản phẩm</span>
      )}
    </Card>
  );
}

function MessageBubble({
  message,
  onAddToCart,
  onViewDetail,
}: {
  message: Message;
  onAddToCart?: (product: Product, size: string, quantity: number) => void;
  onViewDetail?: (product: Product) => void;
}) {
  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] space-y-2 rounded-lg px-3 py-2 text-sm ${
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-muted text-foreground"
        }`}
      >
        <p className="whitespace-pre-wrap">{message.content}</p>

        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="flex flex-wrap gap-1 pt-1">
            {message.toolCalls.map((tc, i) => (
              <Badge key={i} variant="outline" className="text-[10px]">
                🔧 {tc.tool}
              </Badge>
            ))}
          </div>
        )}

        {message.products && message.products.length > 0 && (
          <div className="grid grid-cols-2 gap-2 pt-2 md:grid-cols-3">
            {message.products.map((p) => (
              <div
                key={p.id}
                onClick={(e) => {
                  // Không mở chi tiết khi click vào nút/Select bên trong card
                  const target = e.target as HTMLElement;
                  if (target.closest("button")) return;
                  onViewDetail?.(p);
                }}
                className="cursor-pointer"
              >
                <ProductCard product={p} onAdd={onAddToCart} />
                {onViewDetail && (
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    className="mt-1 h-7 w-full text-xs"
                    onClick={(e) => {
                      e.stopPropagation();
                      onViewDetail(p);
                    }}
                  >
                    <Eye className="mr-1 h-3.5 w-3.5" />
                    Xem chi tiết
                  </Button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
