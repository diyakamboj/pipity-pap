# OpenHands Agent Service

This folder is a standalone OpenHands SDK service separate from the Next.js interface.

## What it provides

- A FastAPI endpoint to accept a user prompt.
- A Python `Conversation` backed by the OpenHands SDK.
- A standard OpenHands tool set:
  - `TerminalTool`
  - `FileEditorTool`
  - `TaskTrackerTool`

## Quick start

1. In this folder, create a Python environment.
2. Install the service package:

   ```bash
   pip install -e .
   ```

3. Copy the sample environment file and fill in your LLM key:

   ```bash
   copy .env.example .env
   ```

4. Start the service:

   ```bash
   python agent_service.py
   ```

   Or:

   ```bash
   uvicorn agent_service:app --host 0.0.0.0 --port 8001
   ```

## API

### `GET /health`
Returns basic service status.

### `POST /run`
Request body:

```json
{
  "prompt": "Write 3 facts about the current project into FACTS.txt."
}
```

Response:

```json
{
  "status": "completed",
  "message": "The OpenHands conversation completed successfully.",
  "workspace": "<current working directory>"
}
```

## Notes

The interface in the main workspace can call this service over HTTP without coupling its UI logic to the OpenHands SDK imports.
