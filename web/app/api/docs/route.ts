import { proxy } from "@/lib/upstream";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const body = await request.text();
  return proxy("/docs", { method: "POST", body });
}
