export function apiBase(): string {
  return (process.env.API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
}

export async function proxy(path: string, init?: RequestInit): Promise<Response> {
  const response = await fetch(`${apiBase()}${path}`, {
    ...init,
    headers: {
      "content-type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  const body = await response.text();
  return new Response(body, {
    status: response.status,
    headers: {
      "content-type": response.headers.get("content-type") || "application/json",
    },
  });
}
