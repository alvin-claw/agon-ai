const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export async function fetchApi<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const { headers: customHeaders, ...restOptions } = options ?? {};
  const res = await fetch(`${API_BASE}${path}`, {
    ...restOptions,
    headers: { "Content-Type": "application/json", ...customHeaders },
  });
  if (!res.ok) throw new Error(`API Error: ${res.status}`);
  return res.json();
}
