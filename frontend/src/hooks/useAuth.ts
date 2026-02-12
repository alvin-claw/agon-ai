"use client";

import { useState, useEffect, useCallback } from "react";
import { getToken, setToken as saveToken, removeToken } from "@/lib/auth";
import type { Developer } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export function useAuth() {
  const [developer, setDeveloper] = useState<Developer | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchMe = useCallback(async () => {
    const token = getToken();
    if (!token) {
      setLoading(false);
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/api/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        setDeveloper(await res.json());
      } else {
        removeToken();
      }
    } catch {
      // ignore network errors
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchMe();
  }, [fetchMe]);

  const login = () => {
    window.location.href = `${API_BASE}/api/auth/github`;
  };

  const logout = () => {
    removeToken();
    setDeveloper(null);
  };

  return {
    developer,
    loading,
    isAuthenticated: !!developer,
    login,
    logout,
    setToken: saveToken,
    refetch: fetchMe,
  };
}
