import { useCallback, useState } from "react";

export interface CustomerProfile {
  phone: string;
  name: string;
  address: string;
}

const PROFILE_KEY = "fashion-chatbot.profile";

function readProfile(): CustomerProfile | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(PROFILE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as CustomerProfile;
    if (!parsed || typeof parsed.phone !== "string") return null;
    return parsed;
  } catch {
    return null;
  }
}

export function useCustomerProfile() {
  const [profile, setProfileState] = useState<CustomerProfile | null>(() => readProfile());

  const save = useCallback((p: CustomerProfile) => {
    if (typeof window === "undefined") return;
    sessionStorage.setItem(PROFILE_KEY, JSON.stringify(p));
    setProfileState(p);
  }, []);

  const clear = useCallback(() => {
    if (typeof window === "undefined") return;
    sessionStorage.removeItem(PROFILE_KEY);
    setProfileState(null);
  }, []);

  const hasPhone = !!profile?.phone;

  return { profile, save, clear, hasPhone };
}
