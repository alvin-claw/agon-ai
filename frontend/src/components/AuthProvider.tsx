"use client";

import { useEffect } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { setToken } from "@/lib/auth";

export function AuthCallbackHandler() {
  const searchParams = useSearchParams();
  const router = useRouter();

  useEffect(() => {
    const token = searchParams.get("token");
    if (token) {
      setToken(token);
      router.replace(window.location.pathname);
    }
  }, [searchParams, router]);

  return null;
}
