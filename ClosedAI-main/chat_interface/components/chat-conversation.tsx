"use client"

import { useEffect, useRef, useState } from "react"
import { ThumbsUp, ThumbsDown, Copy, Check, Download, Eye, FileText, ShieldCheck, Send, X } from "lucide-react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { ChatComposer } from "@/components/chat-composer"
import { AgentActivityFeed } from "@/components/agent-activity-feed"
import { useChat, formatRelativeTime, type Message } from "@/lib/chat-store"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

function MessageFiles({ content }: { content: string }) {
  const [previewOpen, setPreviewOpen] = useState(false)
  const [previewFile, setPreviewFile] = useState<string | null>(null)

  // Match file paths or filenames mentioned in message text
  const fileMatches = Array.from(
    new Set(
      (
        content.match(
          /[a-zA-Z0-9_\-\.\/\\\:]+\.(pdf|docx|xlsx|pptx|txt|json)/gi,
        ) || []
      ).map((f) => f.trim().replace(/^[`'"]+|[`'"]+$/g, "")),
    ),
  ).filter((f) => !f.includes("http://") && !f.includes("https://") && !f.endsWith(".json"))

  if (fileMatches.length === 0) return null

  const openPreview = (f: string) => {
    setPreviewFile(f)
    setPreviewOpen(true)
  }

  return (
    <>
      <div className="mt-2.5 flex flex-wrap gap-2">
        {fileMatches.map((filePath) => {
          const filename = filePath.split(/[\\/]/).pop() || filePath
          const isPdf = filename.toLowerCase().endsWith(".pdf")
          return (
            <div
              key={filePath}
              className="inline-flex items-center gap-2 rounded-lg border border-white/[0.08] bg-white/[0.03] px-2.5 py-1.5 text-xs text-neutral-200"
            >
              <FileText className="h-3.5 w-3.5 text-blue-400 shrink-0" />
              <span className="font-mono text-[12px] truncate max-w-[200px]">{filename}</span>
              <button
                onClick={() => openPreview(filePath)}
                className="ml-1 rounded p-1 text-neutral-400 hover:bg-white/[0.08] hover:text-neutral-100 transition-colors"
                title="Preview document"
              >
                <Eye className="h-3 w-3" />
              </button>
              <a
                href={`/api/workspace/files?path=${encodeURIComponent(filePath)}&download=1`}
                download
                className="rounded p-1 text-neutral-400 hover:bg-white/[0.08] hover:text-neutral-100 transition-colors"
                title="Download document"
              >
                <Download className="h-3 w-3" />
              </a>
            </div>
          )
        })}
      </div>

      <Dialog open={previewOpen} onOpenChange={setPreviewOpen}>
        <DialogContent className="max-w-4xl h-[85vh] flex flex-col p-0 overflow-hidden border-white/10 bg-[#121212] text-neutral-100">
          <DialogHeader className="px-6 py-4 border-b border-white/10 flex flex-row items-center justify-between">
            <DialogTitle className="text-base font-semibold font-mono flex items-center gap-2">
              <FileText className="h-4 w-4 text-blue-400" />
              {previewFile?.split(/[\\/]/).pop() || "Document Preview"}
            </DialogTitle>
            {previewFile && (
              <a
                href={`/api/workspace/files?path=${encodeURIComponent(previewFile)}&download=1`}
                download
                className="inline-flex h-8 items-center justify-center gap-1.5 rounded-md bg-blue-600 px-3 text-xs font-medium text-white hover:bg-blue-500 transition-colors mr-6"
              >
                <Download className="h-3.5 w-3.5" />
                Download
              </a>
            )}
          </DialogHeader>
          <div className="flex-1 bg-[#1a1a1a] p-2 overflow-hidden flex items-center justify-center">
            {previewFile ? (
              <iframe
                src={`/api/workspace/files?path=${encodeURIComponent(previewFile)}&preview=1`}
                className="w-full h-full rounded border-0 bg-white"
                title="Document Preview"
              />
            ) : (
              <p className="text-neutral-500 text-sm">No preview available</p>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}

function ChatApprovalCard({ message }: { message: Message }) {
  const approval = message.metadata?.approval
  const [status, setStatus] = useState<"pending" | "approved" | "rejected" | "error">("pending")
  const [busy, setBusy] = useState(false)
  if (!approval) return null

  const submit = async (accept: boolean) => {
    setBusy(true)
    try {
      const res = await fetch("/api/chat/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          conversationId: approval.conversationId,
          accept,
          reason: accept ? undefined : "User rejected the action.",
        }),
      })
      if (!res.ok) throw new Error("Failed to submit approval")
      setStatus(accept ? "approved" : "rejected")
    } catch {
      setStatus("error")
    } finally {
      setBusy(false)
    }
  }

  const rows =
    approval.toolName === "send_email"
      ? [
          ["To", approval.params.to],
          ["Cc", approval.params.cc],
          ["Subject", approval.params.subject],
        ]
      : approval.toolName === "send_slack_message"
        ? [["Channel", approval.params.channel]]
        : [["Recipient", approval.params.recipient]]

  return (
    <div className="mt-3 w-full max-w-[520px] rounded-xl border border-amber-500/25 bg-amber-500/[0.055] p-3.5">
      <div className="flex items-start gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-amber-500/25 bg-black/20">
          <ShieldCheck className="h-4 w-4 text-amber-300" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <p className="truncate text-[13px] font-semibold text-neutral-100">Approval required</p>
            {approval.risk && (
              <span className="rounded-full border border-amber-500/25 bg-black/20 px-2 py-0.5 text-[10px] font-medium text-amber-200">
                {approval.risk}
              </span>
            )}
          </div>
          <p className="mt-0.5 text-[12px] text-neutral-300">{approval.title}</p>
          <div className="mt-3 space-y-1.5">
            {rows.map(([label, value]) =>
              value ? (
                <div key={label} className="grid grid-cols-[64px_1fr] gap-2 text-[11.5px]">
                  <span className="text-neutral-500">{label}</span>
                  <span className="break-words text-neutral-200">{String(value)}</span>
                </div>
              ) : null,
            )}
          </div>
          <p className="mt-3 text-[11.5px] text-neutral-400">
            Full draft/status is available in the Canvas. Approval happens here in chat.
          </p>
        </div>
      </div>

      {status === "pending" ? (
        <div className="mt-3 flex items-center gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={() => submit(false)}
            className="inline-flex flex-1 items-center justify-center gap-2 rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-[12px] font-medium text-neutral-300 transition-colors hover:bg-white/[0.06] disabled:opacity-50"
          >
            <X className="h-3.5 w-3.5" />
            Reject
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => submit(true)}
            className="inline-flex flex-1 items-center justify-center gap-2 rounded-lg border border-white/15 bg-white/[0.11] px-3 py-2 text-[12px] font-semibold text-neutral-50 transition-colors hover:bg-white/[0.17] disabled:opacity-50"
          >
            <Send className="h-3.5 w-3.5" />
            Approve &amp; Send
          </button>
        </div>
      ) : (
        <div className="mt-3 flex items-center gap-2 rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-[12px] text-neutral-300">
          <Check className="h-3.5 w-3.5" />
          {status === "approved" ? "Approved. Execution can continue." : status === "rejected" ? "Rejected. Nothing was sent." : "Could not submit approval."}
        </div>
      )}
    </div>
  )
}

function MessageActions({ message }: { message: Message }) {
  const { reactToMessage } = useChat()
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      // clipboard may be unavailable; ignore
    }
  }

  return (
    <div className="mt-1 flex items-center gap-3 text-neutral-500">
      <button
        aria-label="Good response"
        aria-pressed={message.reaction === "up"}
        onClick={() => reactToMessage(message.id, "up")}
        className={cn("transition-colors hover:text-neutral-200", message.reaction === "up" && "text-neutral-100")}
      >
        <ThumbsUp className="h-3.5 w-3.5" />
      </button>
      <button
        aria-label="Bad response"
        aria-pressed={message.reaction === "down"}
        onClick={() => reactToMessage(message.id, "down")}
        className={cn("transition-colors hover:text-neutral-200", message.reaction === "down" && "text-neutral-100")}
      >
        <ThumbsDown className="h-3.5 w-3.5" />
      </button>
      <button
        aria-label="Copy message"
        onClick={handleCopy}
        className="transition-colors hover:text-neutral-200"
      >
        {copied ? <Check className="h-3.5 w-3.5 text-neutral-200" /> : <Copy className="h-3.5 w-3.5" />}
      </button>
    </div>
  )
}

export const MARKDOWN_PLUGINS = [remarkGfm]
export const MARKDOWN_COMPONENTS: import("react-markdown").Components = {
  p: ({ node, ...props }) => {
    const hasCodeChild = (node?.children ?? []).some(
      (child: any) => child.type === "element" && child.tagName === "code",
    )
    const Tag = hasCodeChild ? "div" : "p"
    return <Tag className="mb-3 last:mb-0" {...props} />
  },
  ul: ({ node, ...props }) => <ul className="list-disc pl-5 mb-3 last:mb-0 space-y-1.5" {...props} />,
  ol: ({ node, ...props }) => <ol className="list-decimal pl-5 mb-3 last:mb-0 space-y-1.5" {...props} />,
  li: ({ node, ...props }) => <li className="marker:text-neutral-600" {...props} />,
  a: ({ node, ...props }) => (
    <a className="text-blue-400 hover:text-blue-300 hover:underline underline-offset-4 transition-colors" {...props} />
  ),
  strong: ({ node, ...props }) => <strong className="font-semibold text-neutral-100" {...props} />,
  code: ({ node, inline, className, children, ...props }: any) =>
    inline ? (
      <code className="bg-neutral-800/80 text-neutral-200 rounded-md px-1.5 py-0.5 font-mono text-[12px] border border-neutral-700/50" {...props}>
        {children}
      </code>
    ) : (
      <div className="group relative my-4 rounded-xl border border-neutral-800 bg-[#0f0f0f] shadow-sm overflow-hidden">
        <div className="flex items-center justify-between bg-neutral-900/50 px-4 py-2 border-b border-neutral-800">
          <span className="text-[11px] font-medium text-neutral-500 uppercase tracking-wider">Code</span>
        </div>
        <pre className="p-4 overflow-x-auto text-[13px] leading-relaxed">
          <code className="font-mono text-neutral-300" {...props}>
            {children}
          </code>
        </pre>
      </div>
    ),
}

export function ChatConversation() {
  const { activeConversation, reactToMessage } = useChat()
  const scrollRef = useRef<HTMLDivElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [activeConversation.length])

  if (!activeConversation) return null

  return (
    <div className="relative z-10 flex flex-1 flex-col overflow-hidden">
      {/* Live activity feed — pinned above the conversation while the agent works */}
      <AgentActivityFeed />

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        <div className="mx-auto flex max-w-[680px] flex-col gap-6 px-6 py-8">
          <div className="text-center text-[11px] font-medium uppercase tracking-wide text-neutral-500">Today</div>

          {activeConversation.map((message) => {
            const createdAt = message.createdAt ?? message.timestamp?.getTime?.() ?? Date.now()
            return message.role === "user" ? (
              <div key={message.id} className="msg-in flex flex-col items-end gap-1.5">
                <div className="flex items-center gap-2 text-[12px]">
                  <span className="font-semibold text-neutral-200">Me</span>
                  <span className="text-neutral-500">{formatRelativeTime(createdAt)}</span>
                </div>
                <div className="max-w-[85%] rounded-xl rounded-tr-sm bg-[#161616] px-3.5 py-2.5 text-[13.5px] leading-relaxed text-neutral-200 text-pretty">
                  {message.content}
                </div>
              </div>
            ) : (
              <div key={message.id} className="msg-in flex flex-col items-start gap-1.5">
                <div className="flex items-center gap-2 text-[12px]">
                  <span className="font-semibold text-neutral-200">HR Agent</span>
                  <span className="text-neutral-500">{formatRelativeTime(createdAt)}</span>
                </div>
                <div className="max-w-[90%] text-[13.5px] leading-relaxed text-neutral-300 text-pretty">
                  <ReactMarkdown
                    remarkPlugins={MARKDOWN_PLUGINS}
                    components={MARKDOWN_COMPONENTS}
                  >
                    {message.content}
                  </ReactMarkdown>
                  <ChatApprovalCard message={message} />
                  <MessageFiles content={message.content} />
                </div>
                <MessageActions message={message} />
              </div>
            )
          })}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* Composer */}
      <div className="px-6 pb-4">
        <ChatComposer />
        <p className="mt-3 text-center text-[11px] text-neutral-600">
          Luminar is still training models. Please help us improve the results.
        </p>
      </div>
    </div>
  )
}
