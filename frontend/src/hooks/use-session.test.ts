import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { useAdminToken, useSession } from "@/hooks/use-session";

const SESSION_KEY = "fashion-chatbot.session_id";

describe("useSession", () => {
  beforeEach(() => localStorage.clear());

  it("tạo session_id mới và persist vào localStorage", () => {
    const { result } = renderHook(() => useSession());
    expect(result.current.sessionId).toMatch(/^[0-9a-f-]{36}$/);
    expect(localStorage.getItem(SESSION_KEY)).toBe(result.current.sessionId);
  });

  it("reuse session_id đã lưu (giữ phiên tư vấn qua reload)", () => {
    localStorage.setItem(SESSION_KEY, "saved-id");
    const { result } = renderHook(() => useSession());
    expect(result.current.sessionId).toBe("saved-id");
  });

  it("reset sinh id mới và ghi đè storage", () => {
    const { result } = renderHook(() => useSession());
    const first = result.current.sessionId;
    act(() => result.current.reset());
    expect(result.current.sessionId).not.toBe(first);
    expect(localStorage.getItem(SESSION_KEY)).toBe(result.current.sessionId);
  });
});

describe("useAdminToken", () => {
  beforeEach(() => sessionStorage.clear());

  it("save lưu sessionStorage, clear xoá", () => {
    const { result } = renderHook(() => useAdminToken());
    expect(result.current.token).toBeNull();
    act(() => result.current.save("tok"));
    expect(result.current.token).toBe("tok");
    expect(sessionStorage.getItem("fashion-chatbot.admin_token")).toBe("tok");
    act(() => result.current.clear());
    expect(result.current.token).toBeNull();
    expect(sessionStorage.getItem("fashion-chatbot.admin_token")).toBeNull();
  });
});
