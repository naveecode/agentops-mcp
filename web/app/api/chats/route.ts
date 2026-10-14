import { proxy } from "@/lib/upstream";

export const dynamic = "force-dynamic";

export function GET() {
  return proxy("/chats");
}
