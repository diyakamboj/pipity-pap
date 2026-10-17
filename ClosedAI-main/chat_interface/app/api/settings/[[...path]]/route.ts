import { NextRequest } from "next/server"
import { proxyToBackend } from "@/lib/backend-proxy"

/* Proxy for /api/settings/* -> backend /api/settings/*
 * (GET/PATCH /api/settings, secrets CRUD at /api/settings/secrets). */

export async function GET(request: NextRequest) {
  return proxyToBackend(request, "settings")
}

export async function PATCH(request: NextRequest) {
  return proxyToBackend(request, "settings")
}

export async function PUT(request: NextRequest) {
  return proxyToBackend(request, "settings")
}

export async function POST(request: NextRequest) {
  return proxyToBackend(request, "settings")
}

export async function DELETE(request: NextRequest) {
  return proxyToBackend(request, "settings")
}
