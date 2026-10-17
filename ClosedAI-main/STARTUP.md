# AI HR Copilot — Startup Guide

How to boot the whole system on Windows (PowerShell). There are **two long‑running
processes**: the Python **backend** (HRAgents agent server) and the Next.js
**frontend** (HR Copilot UI). The HR data tools (`hr-mcp`) start **automatically** as a
subprocess of the backend — you don't launch them yourself.

```
ClosedAI/
├─ HRAgent_Main/     ← backend (FastAPI agent server) — Terminal 1
├─ frontend/         ← frontend (Next.js UI)          — Terminal 2
├─ hr_mcp/           ← HR data tools (auto-spawned by the backend)
└─ chat_interface/   ← previous UI (kept for reference; not used at runtime)
```

---

## First-time setup (once per machine)

Run these once. If you've already used the app, skip to **Daily boot-up**.

1. **Backend Python environment** (needs [`uv`](https://docs.astral.sh/uv/) and Python 3.13):

   ```powershell
   cd "C:\Users\ishaa\OneDrive - UW\Academic\Coding\ClosedAI\HRAgent_Main"
   uv sync
   ```

   This creates `HRAgent_Main\.venv` with all backend deps (including `fastmcp`,
   which `hr-mcp` needs).

2. **Frontend Node dependencies** (needs Node 18+):

   ```powershell
   cd "C:\Users\ishaa\OneDrive - UW\Academic\Coding\ClosedAI\frontend"
   npm install
   ```

3. **Frontend environment file** — `frontend\.env.local` is configured for **TokenRouter**:

   ```
   LLM_PROVIDER=tokenrouter
   TOKENROUTER_API_KEY=sk-v8NoCrajDilDlx1k53N2q8Iwevt3Jv0FLzL6xllGd0Xvi3jV
   TOKENROUTER_BASE_URL=https://api.tokenrouter.com/v1
   TOKENROUTER_MODEL=moonshotai/kimi-k3-free
   ```


---

## Daily boot-up (every time)

Open **two** PowerShell terminals.

### Terminal 1 — Backend (start this first)

```powershell
cd "C:\Users\ishaa\OneDrive - UW\Academic\Coding\ClosedAI\HRAgent_Main"
.\start_server.ps1
```

Wait until you see: `Uvicorn running on http://127.0.0.1:8001`.

> Always use `start_server.ps1` — it forces UTF-8 mode (`PYTHONUTF8=1`), without
> which the backend crashes on emojis/em-dashes on Windows.

### Terminal 2 — Frontend

```powershell
cd "C:\Users\ishaa\OneDrive - UW\Academic\Coding\ClosedAI\frontend"
npm run dev
```

Wait until you see: `Ready` and `Local: http://localhost:3000`.

### Open the app

Go to **<http://localhost:3000>** in your browser (Intake is the default home).
Use **New task** (or open **<http://localhost:3000/chat>**) and try:

- `What is Sarah Chen's PTO balance?` → PTO card appears in the Side Canvas.
- `Show me Marcus Johnson's org chart` → org-chart module.
- `Draft an email to sarah.chen@example.com about the PTO policy` → an
  **Approve & Send** card appears on the canvas (nothing sends until you click).

---

## Shutting down

In each terminal press **Ctrl+C**. That's it — closing the terminals also stops
the processes.

---

## Troubleshooting

- **UI error "Could not connect / create conversation"** → the backend (Terminal 1)
  isn't running or didn't finish starting. Confirm `http://127.0.0.1:8001` is up.
- **`[winerror 10048] only one usage of each socket address`** → an old backend is
  still holding port 8001. Find and stop it, then restart:

  ```powershell
  Get-NetTCPConnection -LocalPort 8001 | Select-Object -Expand OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force }
  ```

- **Port 3000 in use / "Unable to acquire lock"** → another `next dev` is already
  running. Either use the URL it printed, or stop stray Node dev servers:

  ```powershell
  Get-CimInstance Win32_Process -Filter "Name='node.exe'" | Where-Object { $_.CommandLine -like '*next*dev*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
  ```

- **`429 RESOURCE_EXHAUSTED` / rate limit** → the LLM key is out of quota. Get a
  fresh Groq key and update `GROQ_API_KEY` in `.env.local`, then **restart the
  frontend** (env is only read at startup).
- **Changed `.env.local`?** → restart Terminal 2 (`npm run dev`). Code changes hot-
  reload, but env changes do not.
- **Side Canvas / tools not working** → ensure `hr_mcp` deps exist in the backend
  venv (`uv sync` in `HRAgent_Main`). The backend logs a `[hr-mcp] disabled: ...`
  warning if it can't find the tool server or its Python.

---

## Optional: command-line smoke test

Verifies the backend + agent + tools without the browser (needs both servers up):

```powershell
cd "C:\Users\ishaa\OneDrive - UW\Academic\Coding\ClosedAI\frontend"
node scripts/hr-test.mjs "What is Sarah Chen's PTO balance?"
```

You should see `ACTION → pto_balance`, `OBSERVATION ←`, and a grounded `FINAL:` answer.

## Switching LLM provider (TokenRouter → Groq / OpenAI / Azure)

No code changes — edit `frontend\.env.local`, then restart the frontend:

- **TokenRouter:** `LLM_PROVIDER=tokenrouter`, set `TOKENROUTER_API_KEY`, `TOKENROUTER_BASE_URL` (default `https://api.tokenrouter.com/v1`), `TOKENROUTER_MODEL` (default `moonshotai/kimi-k3-free`).
- **Groq:** `LLM_PROVIDER=groq`, set `GROQ_API_KEY=gsk-...` (model `GROQ_MODEL`, default `llama-3.3-70b-versatile`).
- **OpenAI:** `LLM_PROVIDER=openai`, set `OPENAI_API_KEY=sk-...` (model `OPENAI_MODEL`, default `gpt-4o`).
- **Azure OpenAI:** `LLM_PROVIDER=azure`, set `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`,
  `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION`.
- **Azure AI Foundry serverless (e.g. GPT-5.2):** Foundry's serverless endpoints are
  OpenAI-compatible, so **use the `openai` provider, not `azure`** (the backend's `azure/`
  LiteLLM path only understands classic `openai.azure.com` resources and 404s on Foundry).
  ```
  LLM_PROVIDER=openai
  OPENAI_API_KEY=<key>
  OPENAI_MODEL=gpt-5.2
  OPENAI_BASE_URL=https://<project>.<region>.services.ai.azure.com/openai/v1
  ```
  The backend auto-routes `gpt-5.2` through the Responses API, so the base URL is the
  `/openai/v1` root — do **not** include the `/responses` suffix (LiteLLM appends it).

### Foundry key/endpoint (project-specific)

The Azure OpenAI key for Foundry lives in the **`group-1` Key Vault** (resource group `AI_Keys`):
- Secret `Group1OpenAIAPIKey` → the API key value (read via
  `az keyvault secret show --vault-name group-1 --name Group1OpenAIAPIKey --query value -o tsv`).
- Secret `Group1OpenAIEndPoint` → `https://sharedfoundry.services.ai.azure.com/openai/v1/responses`
  (strip the trailing `/responses` for `OPENAI_BASE_URL`).
- Endpoint auth accepts both `api-key:` and `Authorization: Bearer` headers.
