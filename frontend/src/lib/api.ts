const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export async function fetchApi<T>(
  path: string,
  options?: RequestInit & { auth?: boolean },
): Promise<T> {
  const { headers: customHeaders, auth, ...restOptions } = options ?? {};
  const authHeaders = auth ? (await import("./auth")).getAuthHeaders() : {};
  const res = await fetch(`${API_BASE}${path}`, {
    ...restOptions,
    headers: { "Content-Type": "application/json", ...authHeaders, ...customHeaders },
  });
  if (!res.ok) throw new Error(`API Error: ${res.status}`);
  return res.json();
}
