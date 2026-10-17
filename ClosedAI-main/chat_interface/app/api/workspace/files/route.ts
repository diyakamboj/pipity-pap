import { NextRequest, NextResponse } from "next/server"
import path from "node:path"
import fs from "node:fs"

// Base directory for agent workspace files
const REPO_ROOT = path.resolve(process.cwd(), "..")
const WORKSPACE_DIR = path.join(REPO_ROOT, "HRAgent_Main", "workspace")

const MIME_TYPES: Record<string, string> = {
  ".pdf": "application/pdf",
  ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  ".txt": "text/plain; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".md": "text/markdown; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
}

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url)
  const rawPath = searchParams.get("path")
  const download = searchParams.get("download") === "1"

  if (!rawPath) {
    return NextResponse.json({ error: "Missing path parameter" }, { status: 400 })
  }

  // Normalize path and resolve against workspace directory
  let resolvedPath: string
  if (path.isAbsolute(rawPath)) {
    // If it's already an absolute path inside the workspace or repo
    resolvedPath = path.normalize(rawPath)
  } else {
    resolvedPath = path.resolve(WORKSPACE_DIR, rawPath)
  }

  // Security check: ensure path is within repo or workspace to prevent arbitrary file access
  const isWithinWorkspace = resolvedPath.startsWith(WORKSPACE_DIR)
  const isWithinRepo = resolvedPath.startsWith(REPO_ROOT)
  if (!isWithinWorkspace && !isWithinRepo) {
    return NextResponse.json({ error: "Access denied: path outside workspace" }, { status: 403 })
  }

  if (!fs.existsSync(resolvedPath)) {
    return NextResponse.json({ error: "File not found" }, { status: 404 })
  }

  const stat = fs.statSync(resolvedPath)
  if (!stat.isFile()) {
    return NextResponse.json({ error: "Target is not a file" }, { status: 400 })
  }

  const filename = path.basename(resolvedPath)
  const ext = path.extname(resolvedPath).toLowerCase()
  const contentType = MIME_TYPES[ext] || "application/octet-stream"

  const fileStream = fs.readFileSync(resolvedPath)

  const headers = new Headers()
  headers.set("Content-Type", contentType)
  headers.set("Content-Length", String(stat.size))
  headers.set(
    "Content-Disposition",
    `${download ? "attachment" : "inline"}; filename="${encodeURIComponent(filename)}"`,
  )

  return new NextResponse(fileStream, {
    status: 200,
    headers,
  })
}
