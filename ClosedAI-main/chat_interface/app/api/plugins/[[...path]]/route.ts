import { NextRequest } from "next/server"
import { proxyToBackend } from "@/lib/backend-proxy"

/* Proxy for /api/plugins/* -> backend /api/plugins/*
 * (POST /api/plugins, POST /api/plugins/install,
 *  GET /api/plugins/installed[/{name}], GET /api/plugins/marketplace,
 *  PATCH/DELETE /api/plugins/installed/{name},
 *  POST /api/plugins/installed/{name}/refresh). */

export async function GET(request: NextRequest) {
  return proxyToBackend(request, "plugins")
}

export async function POST(request: NextRequest) {
  return proxyToBackend(request, "plugins")
}

export async function PATCH(request: NextRequest) {
  return proxyToBackend(request, "plugins")
}

export async function DELETE(request: NextRequest) {
  return proxyToBackend(request, "plugins")
}
