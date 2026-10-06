import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ProductCard } from "@/components/ProductCard";
import type { Product } from "@/types";

const product = (over: Partial<Product> = {}): Product => ({
  id: "P001",
  name: "Áo sơ mi đen basic",
  brand: "Maison Étoile",
  category: "áo",
  description: "Áo sơ mi công sở.",
  price_vnd: 450000,
  sizes_available: ["S", "M", "L"],
  colors: ["đen"],
  material: "cotton",
  stock_per_size: { S: 2, M: 0, L: 5 },
  tags: ["cong-so"],
  image_url: "https://example.invalid/a.png",
  gender: "nam",
  created_at: new Date().toISOString(),
  ...over,
});

describe("ProductCard", () => {
  it("render tên, brand, giá", () => {
    render(<ProductCard product={product()} />);
    expect(screen.getByText("Áo sơ mi đen basic")).toBeInTheDocument();
    expect(screen.getByText("Maison Étoile")).toBeInTheDocument();
    expect(screen.getByText(/450[.,]000/)).toBeInTheDocument();
  });

  it("khi hết hàng mọi size → nút 'Thêm vào giỏ' bị khoá", () => {
    render(
      <ProductCard
        product={product({ stock_per_size: { S: 0, M: 0, L: 0 } })}
        onAdd={() => {}}
      />
    );
    expect(screen.getByRole("button", { name: /thêm vào giỏ/i })).toBeDisabled();
  });
  it("click 'Thêm vào giỏ' gọi onAdd với size mặc định còn hàng + qty 1", () => {
    const onAdd = vi.fn();
    const p = product();
    render(<ProductCard product={p} onAdd={onAdd} />);
    fireEvent.click(screen.getByRole("button", { name: /thêm vào giỏ/i }));
    // size mặc định = size còn hàng ĐẦU TIÊN trong danh sách (S; M stock=0)
    expect(onAdd).toHaveBeenCalledWith(p, "S", 1);
  });

  it("người dùng đổi size → onAdd nhận size đã chọn; size hết hàng bị disable", async () => {
    const onAdd = vi.fn();
    const p = product();
    const user = userEvent.setup();
    render(<ProductCard product={p} onAdd={onAdd} />);
    await user.click(screen.getByRole("combobox"));
    await waitFor(() => expect(screen.getByRole("listbox")).toBeInTheDocument());
    // Radix option không phải <option> native → check qua data-disabled
    expect(screen.getByRole("option", { name: /M/ })).toHaveAttribute("data-disabled");
    await user.click(screen.getByRole("option", { name: /^L/ }));
    await waitFor(() => expect(screen.queryByRole("listbox")).not.toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /thêm vào giỏ/i }));
    expect(onAdd).toHaveBeenCalledWith(p, "L", 1);
  });
});
