import { describe, expect, it } from "vitest";
import { cn, formatVnd } from "@/lib/utils";

describe("formatVnd", () => {
  it("định dạng VND theo locale vi-VN, không thập phân", () => {
    expect(formatVnd(450000)).toMatch(/450[.,]000\s?₫/);
    expect(formatVnd(0)).toMatch(/0\s?₫/);
  });

  it("làm tròn số lẻ (product chỉ dùng int nhưng API có thể trả float)", () => {
    expect(formatVnd(123456.7)).toContain("123");
  });
});

describe("cn", () => {
  it("gộp class có điều kiện", () => {
    expect(cn("a", false && "b", "c")).toBe("a c");
  });

  it("resolve xung đột tailwind (merge, không nối chuỗi)", () => {
    expect(cn("p-2", "p-4")).toBe("p-4");
  });
});
