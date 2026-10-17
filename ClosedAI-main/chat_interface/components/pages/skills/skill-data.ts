import {
  Code2,
  FileText,
  BarChart3,
  AlertCircle,
  FileEdit,
  Headphones,
  CircleDot,
  GitBranch,
  Database,
  Search as SearchIcon,
  MessageSquare,
  Boxes,
  ShieldCheck,
  Terminal,
} from "lucide-react"
import type {
  ActivityStatus,
  Skill,
  SkillActivity,
  SkillPermissionFlags,
  SkillPermissions,
  SkillTemplate,
  SkillVariable,
} from "./skill-types"

const now = Date.now()

/* ---------- small helpers ---------- */

export function rel(minutesAgo: number): string {
  if (minutesAgo < 1) return "just now"
  if (minutesAgo < 60) return `${minutesAgo} min ago`
  const hours = Math.floor(minutesAgo / 60)
  if (hours < 24) return `${hours} hr ago`
  return `${Math.floor(hours / 24)} d ago`
}

export function uid(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID()
  return `id-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function act(action: string, detail: string, minutesAgo: number, status: ActivityStatus): SkillActivity {
  return { id: `a-${uid()}`, action, detail, time: rel(minutesAgo), ts: now - minutesAgo * 60_000, status }
}

export function defaultFlags(): SkillPermissionFlags {
  return {
    requireConfirmation: false,
    allowFileWrite: true,
    allowNetwork: true,
    allowDbMutations: false,
    allowShellCommands: false,
  }
}

export function defaultPermissions(): SkillPermissions {
  return { flags: defaultFlags(), toolOverrides: {} }
}

export function todayLabel(): string {
  return new Date().toLocaleDateString("en-US", { month: "short", day: "2-digit", year: "numeric" })
}

export const CATEGORY_ICONS = {
  Engineering: GitBranch,
  Productivity: FileText,
  Research: SearchIcon,
  Communication: MessageSquare,
  Data: Database,
  Custom: Boxes,
} as const

export function categoryIcon(category: string) {
  return (CATEGORY_ICONS[category as keyof typeof CATEGORY_ICONS] ?? CircleDot) as typeof CircleDot
}

/* ---------- initial skills ---------- */

export const INITIAL_SKILLS: Skill[] = [
  {
    id: "skill-pr-review",
    name: "Pull Request Reviewer",
    description: "Reviews open pull requests, summarizes changes, and flags risky diffs.",
    category: "Engineering",
    scope: "global",
    triggerType: "Trigger-based",
    keywords: ["pr", "pull request", "review", "diff"],
    enabled: true,
    version: "1.4.2",
    author: "northwind-labs",
    requiredTools: ["GitHub", "code-review"],
    instructions:
      "When asked to review a PR, fetch the diff via GitHub, summarize the intent, list risks, and suggest concrete improvements. Always cite the file and line.\n\nSteps:\n1. list_repos to find the repository\n2. Read the PR description and diff\n3. Group comments into blocking and non-blocking\n4. Post a structured summary back to the thread",
    variables: [
      { key: "pr_url", label: "Pull request URL", description: "Full URL of the PR to review.", required: true },
      { key: "depth", label: "Review depth", description: "blocking | all | summary", required: false },
    ],
    added: "Jan 11, 2026",
    lastUsed: "2 hr ago",
    lastUsedTs: now - 120 * 60_000,
    runCount: 47,
    successRate: 96,
    avgDurationMs: 8400,
    errors24h: 1,
    permissions: {
      flags: { ...defaultFlags(), requireConfirmation: true },
      toolOverrides: { GitHub: { tool: "GitHub", allowed: true, requiresConfirmation: false } },
    },
    activity: [
      act("Ran skill", "Reviewed PR #482 — 14 comments posted", 120, "success"),
      act("Ran skill", "Reviewed PR #477 — 6 comments posted", 300, "success"),
      act("Tool denied", "search_code blocked by permission policy", 360, "warning"),
      act("Ran skill", "Reviewed PR #469 — 22 comments posted", 600, "success"),
      act("Ran skill", "Reviewed PR #461 — timed out at 45s", 1440, "error"),
      act("Version updated", "1.4.1 → 1.4.2 published", 2880, "info"),
    ],
  },
  {
    id: "skill-ssh-microagent",
    name: "SSH Microagent",
    description: "Manages SSH connections to remote servers and executes commands.",
    category: "Engineering",
    scope: "workspace",
    triggerType: "Trigger-based",
    keywords: ["ssh", "server", "remote", "command"],
    enabled: true,
    version: "0.9.3",
    author: "infra-team",
    requiredTools: ["SSH", "remote server", "fs"],
    instructions:
      "Connect to remote servers via SSH. Execute commands safely. Always verify connection before running destructive operations.\n\nRules:\n- Never run rm -rf without a confirmation\n- Log every command to the session transcript\n- Disconnect cleanly when done",
    variables: [
      { key: "host", label: "Host", description: "Hostname or IP of the target server.", required: true },
      { key: "command", label: "Command", description: "The command to execute.", required: true },
    ],
    added: "Jan 15, 2026",
    lastUsed: "18 min ago",
    lastUsedTs: now - 18 * 60_000,
    runCount: 89,
    successRate: 91,
    avgDurationMs: 3100,
    errors24h: 3,
    permissions: {
      flags: { ...defaultFlags(), allowFileWrite: true, requireConfirmation: true, allowShellCommands: true },
      toolOverrides: {
        SSH: { tool: "SSH", allowed: true, requiresConfirmation: true },
        "remote server": { tool: "remote server", allowed: true, requiresConfirmation: true },
      },
    },
    activity: [
      act("Ran skill", "Executed deploy script on prod-03", 18, "success"),
      act("Connection error", "SSH handshake failed for staging-01 (retry)", 140, "error"),
      act("Ran skill", "Collected logs from api-01", 300, "success"),
      act("Ran skill", "Executed 3 diagnostic commands", 600, "success"),
      act("Version updated", "0.9.2 → 0.9.3 published", 2880, "info"),
    ],
  },
  {
    id: "skill-agent-memory",
    name: "agent_memory",
    description: "Manages persistent agent memory for context retention across sessions.",
    category: "Data",
    scope: "global",
    triggerType: "Always active",
    keywords: ["memory", "remember", "context"],
    enabled: true,
    version: "2.1.0",
    author: "core",
    requiredTools: ["memory-store"],
    instructions:
      "Store and retrieve agent memories. Prioritize recent and relevant memories. Clean up stale entries periodically.",
    variables: [
      { key: "memory_key", label: "Key", description: "The lookup key for this memory.", required: true },
      { key: "retention_days", label: "Retention (days)", description: "How long to keep the entry.", required: false },
    ],
    added: "Jan 05, 2026",
    lastUsed: "5 min ago",
    lastUsedTs: now - 5 * 60_000,
    runCount: 241,
    successRate: 99,
    avgDurationMs: 340,
    errors24h: 0,
    permissions: defaultPermissions(),
    activity: [
      act("Ran skill", "Stored 12 new memories", 5, "success"),
      act("Ran skill", "Recalled 34 memories for session", 60, "success"),
      act("Maintenance", "Pruned 209 stale entries", 240, "info"),
      act("Ran skill", "Recalled 9 memories for session", 480, "success"),
    ],
  },
  {
    id: "skill-code-review",
    name: "code-review",
    description: "Performs automated code reviews with quality and security analysis.",
    category: "Engineering",
    scope: "global",
    triggerType: "Trigger-based",
    keywords: ["code review", "quality", "security"],
    enabled: true,
    version: "3.2.1",
    author: "platform",
    requiredTools: ["codereview", "GitHub"],
    instructions:
      "Analyze code for bugs, security issues, and style. Provide specific, actionable feedback with severity levels.",
    variables: [
      { key: "scope", label: "Scope", description: "File, diff, or directory to review.", required: true },
      { key: "severity", label: "Min severity", description: "critical | high | medium | low", required: false },
    ],
    added: "Dec 15, 2025",
    lastUsed: "30 min ago",
    lastUsedTs: now - 30 * 60_000,
    runCount: 156,
    successRate: 97,
    avgDurationMs: 5200,
    errors24h: 0,
    permissions: defaultPermissions(),
    activity: [
      act("Ran skill", "Reviewed diff of 32 files", 30, "success"),
      act("Ran skill", "Found 4 security issues", 150, "success"),
      act("Ran skill", "Reviewed diff of 9 files", 400, "success"),
      act("Version updated", "3.2.0 → 3.2.1 published", 2880, "info"),
    ],
  },
  {
    id: "skill-meeting-summary",
    name: "Meeting Summarizer",
    description: "Converts meeting transcripts into structured summaries with action items and owners.",
    category: "Productivity",
    scope: "workspace",
    triggerType: "Keyword",
    keywords: ["summary", "meeting", "notes", "transcript"],
    enabled: true,
    version: "1.1.0",
    author: "ops",
    requiredTools: ["Slack", "Web Search"],
    instructions:
      "Parse the meeting transcript, extract key discussion points, decisions made, and action items with assigned owners and deadlines. Format as a structured summary with clear sections.",
    variables: [
      { key: "transcript", label: "Transcript", description: "Raw meeting transcript text.", required: true },
      { key: "format", label: "Format", description: "bullets | sections | narrative", required: false },
    ],
    added: "Jan 18, 2026",
    lastUsed: "1 d ago",
    lastUsedTs: now - 1440 * 60_000,
    runCount: 23,
    successRate: 94,
    avgDurationMs: 6800,
    errors24h: 0,
    permissions: {
      flags: { ...defaultFlags(), requireConfirmation: true },
      toolOverrides: { Slack: { tool: "Slack", allowed: true, requiresConfirmation: false } },
    },
    activity: [
      act("Ran skill", "Summarized weekly sync (12 attendees)", 1440, "success"),
      act("Ran skill", "Summarized planning call", 2880, "success"),
      act("Version updated", "1.0.0 → 1.1.0 published", 4320, "info"),
    ],
  },
  {
    id: "skill-data-analyst",
    name: "Data Analyst",
    description: "Answers data questions by writing and running SQL queries against connected databases.",
    category: "Data",
    scope: "workspace",
    triggerType: "Trigger-based",
    keywords: ["sql", "query", "data", "analytics"],
    enabled: true,
    version: "2.0.4",
    author: "data-team",
    requiredTools: ["Postgres Database"],
    instructions:
      "Translate the user's data question into an efficient SQL query. Always use read-only operations. Explain the query logic, present results in a clear table, and provide a brief analysis of the findings.",
    variables: [
      { key: "question", label: "Question", description: "The business question to answer.", required: true },
      { key: "table_hint", label: "Table hint", description: "Optional schema hint.", required: false },
    ],
    added: "Dec 30, 2025",
    lastUsed: "3 hr ago",
    lastUsedTs: now - 180 * 60_000,
    runCount: 38,
    successRate: 88,
    avgDurationMs: 4500,
    errors24h: 2,
    permissions: {
      flags: { ...defaultFlags(), requireConfirmation: true, allowDbMutations: false },
      toolOverrides: {
        "Postgres Database": { tool: "Postgres Database", allowed: true, requiresConfirmation: true },
      },
    },
    activity: [
      act("Ran skill", "Answered 'ARPU by month' — 5 rows returned", 180, "success"),
      act("Query rejected", "run_query blocked: INSERT attempted", 300, "error"),
      act("Ran skill", "Answered 'churn by cohort' — 12 rows returned", 420, "success"),
      act("Ran skill", "Query timed out at 30s", 900, "error"),
    ],
  },
  {
    id: "skill-incident",
    name: "Incident Responder",
    description: "Triages production incidents by pulling logs, metrics, and recent deployments.",
    category: "Engineering",
    scope: "workspace",
    triggerType: "Keyword",
    keywords: ["incident", "outage", "pager", "on-call"],
    enabled: true,
    version: "1.3.7",
    author: "sre",
    requiredTools: ["GitHub", "Web Search", "metrics"],
    instructions:
      "When an incident is reported, gather relevant logs and error data. Identify the likely root cause, suggest immediate mitigation steps, and draft an incident timeline. Escalate if the blast radius exceeds the defined threshold.",
    variables: [
      { key: "incident_id", label: "Incident ID", description: "e.g. INC-2091", required: true },
      { key: "severity", label: "Severity", description: "SEV1 | SEV2 | SEV3", required: false },
    ],
    added: "Nov 20, 2025",
    lastUsed: "4 hr ago",
    lastUsedTs: now - 240 * 60_000,
    runCount: 12,
    successRate: 83,
    avgDurationMs: 21000,
    errors24h: 0,
    permissions: {
      flags: { ...defaultFlags(), requireConfirmation: true, allowNetwork: true },
      toolOverrides: {
        "Web Search": { tool: "Web Search", allowed: true, requiresConfirmation: false },
      },
    },
    activity: [
      act("Ran skill", "Triaged INC-2091 — root cause identified", 240, "success"),
      act("Ran skill", "Drafted incident timeline for INC-2088", 800, "success"),
      act("Ran skill", "Escalated INC-2085 to SEV1", 1600, "warning"),
      act("Version updated", "1.3.6 → 1.3.7 published", 4320, "info"),
    ],
  },
  {
    id: "skill-default-tools",
    name: "default-tools",
    description: "Core set of default tools that are always available to the agent.",
    category: "Productivity",
    scope: "global",
    triggerType: "Always active",
    keywords: ["default", "core", "base"],
    enabled: true,
    version: "5.0.0",
    author: "core",
    requiredTools: [],
    instructions: "Provide standard agent capabilities. These tools are always available.",
    variables: [],
    added: "Dec 01, 2025",
    lastUsed: "just now",
    lastUsedTs: now,
    runCount: 1024,
    successRate: 100,
    avgDurationMs: 120,
    errors24h: 0,
    permissions: defaultPermissions(),
    activity: [
      act("Ran skill", "Loaded 42 core tools", 1, "success"),
      act("Ran skill", "Loaded 42 core tools", 60, "success"),
      act("Version updated", "4.9.0 → 5.0.0 published", 10080, "info"),
    ],
  },
]

/* ---------- templates ---------- */

export const SKILL_TEMPLATES: SkillTemplate[] = [
  {
    id: "tpl-code-review",
    name: "Code Reviewer",
    description: "Reviews code for quality, security vulnerabilities, and adherence to team coding standards.",
    category: "Engineering",
    triggerType: "Trigger-based",
    instructions:
      "When presented with code, analyze it for bugs, security issues, performance problems, and style inconsistencies. Provide specific, actionable feedback with suggested fixes. Reference team coding standards when available.",
    requiredTools: ["GitHub"],
    variables: [
      { key: "scope", label: "Scope", description: "File, diff, or directory to review.", required: true },
      { key: "severity", label: "Min severity", description: "critical | high | medium | low", required: false },
    ],
    icon: Code2,
  },
  {
    id: "tpl-meeting-summary",
    name: "Meeting Summarizer",
    description: "Converts meeting transcripts into structured summaries with action items and owners.",
    category: "Productivity",
    triggerType: "Keyword",
    instructions:
      "Parse the meeting transcript, extract key discussion points, decisions made, and action items with assigned owners and deadlines. Format as a structured summary with clear sections.",
    requiredTools: ["Slack"],
    variables: [
      { key: "transcript", label: "Transcript", description: "Raw meeting transcript text.", required: true },
      { key: "format", label: "Format", description: "bullets | sections | narrative", required: false },
    ],
    icon: FileText,
  },
  {
    id: "tpl-data-analyst",
    name: "Data Analyst",
    description: "Answers data questions by writing and running SQL queries against connected databases.",
    category: "Data",
    triggerType: "Trigger-based",
    instructions:
      "Translate the user's data question into an efficient SQL query. Always use read-only operations. Explain the query logic, present results in a clear table, and provide a brief analysis of the findings.",
    requiredTools: ["Postgres Database"],
    variables: [
      { key: "question", label: "Question", description: "The business question to answer.", required: true },
      { key: "table_hint", label: "Table hint", description: "Optional schema hint.", required: false },
    ],
    icon: BarChart3,
  },
  {
    id: "tpl-incident",
    name: "Incident Responder",
    description: "Triages production incidents by pulling logs, metrics, and recent deployments.",
    category: "Engineering",
    triggerType: "Keyword",
    instructions:
      "When an incident is reported, gather relevant logs and error data. Identify the likely root cause, suggest immediate mitigation steps, and draft an incident timeline. Escalate if the blast radius exceeds the defined threshold.",
    requiredTools: ["GitHub", "Postgres Database", "Web Search"],
    variables: [
      { key: "incident_id", label: "Incident ID", description: "e.g. INC-2091", required: true },
      { key: "severity", label: "Severity", description: "SEV1 | SEV2 | SEV3", required: false },
    ],
    icon: AlertCircle,
  },
  {
    id: "tpl-content",
    name: "Content Writer",
    description: "Produces blog posts, documentation, and marketing copy in the company voice.",
    category: "Communication",
    triggerType: "Trigger-based",
    instructions:
      "Write content that matches the company's tone and style guide. Research the topic thoroughly, include relevant data points, and structure the content with clear headings. Always provide a draft outline before writing the full piece.",
    requiredTools: ["Web Search"],
    variables: [
      { key: "topic", label: "Topic", description: "What to write about.", required: true },
      { key: "tone", label: "Tone", description: "professional | casual | playful", required: false },
    ],
    icon: FileEdit,
  },
  {
    id: "tpl-support",
    name: "Customer Support",
    description: "Handles tier-1 customer support queries using the knowledge base and account data.",
    category: "Communication",
    triggerType: "Keyword",
    instructions:
      "Respond to customer queries using the knowledge base. Be empathetic and concise. If the issue cannot be resolved at tier-1, escalate with a summary of the customer's problem and steps already taken.",
    requiredTools: ["Postgres Database"],
    variables: [
      { key: "query", label: "Customer query", description: "What the customer asked.", required: true },
      { key: "account_id", label: "Account ID", description: "Optional account identifier.", required: false },
    ],
    icon: Headphones,
  },
]

export const AVAILABLE_CONNECTIONS = [
  { name: "GitHub", type: "HTTP", installed: true },
  { name: "Postgres Database", type: "Stdio", installed: true },
  { name: "Web Search", type: "SSE", installed: true },
  { name: "Slack", type: "HTTP", installed: false },
  { name: "metrics", type: "HTTP", installed: false },
  { name: "memory-store", type: "Internal", installed: true },
  { name: "SSH", type: "Stdio", installed: true },
  { name: "codereview", type: "Internal", installed: true },
  { name: "fs", type: "Internal", installed: false },
] as const
