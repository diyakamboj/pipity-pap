import { NextRequest } from "next/server"
import { proxyToBackend } from "@/lib/backend-proxy"

/* Proxy for /api/mcp/* -> backend /api/mcp/*
 * (POST /api/mcp/test, POST /api/mcp/oauth/start,
 *  GET /api/mcp/oauth/status/{id}, POST /api/mcp/oauth/callback/{id}). */

export async function GET(request: NextRequest) {
  return proxyToBackend(request, "mcp")
}

export async function POST(request: NextRequest) {
  return proxyToBackend(request, "mcp")
}
