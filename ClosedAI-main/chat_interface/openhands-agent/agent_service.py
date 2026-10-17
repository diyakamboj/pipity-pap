import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from uvicorn import run as uvicorn_run

app = FastAPI(title="OpenHands Agent Service")


class RunRequest(BaseModel):
    prompt: str = Field(..., min_length=1)


class RunResponse(BaseModel):
    status: str
    message: str
    workspace: str


def create_conversation() -> "Conversation":
    from openhands.sdk import Agent, Conversation, LLM, Tool
    from openhands.tools.file_editor import FileEditorTool
    from openhands.tools.task_tracker import TaskTrackerTool
    from openhands.tools.terminal import TerminalTool

    api_key = os.getenv("LLM_API_KEY")
    model = os.getenv("OPENHANDS_MODEL", "gpt-5.5")
    if not api_key:
        raise RuntimeError("LLM_API_KEY is required. Copy .env.example to .env and add a valid key.")

    llm = LLM(model=model, api_key=api_key)
    agent = Agent(
        llm=llm,
        tools=[
            Tool(name=TerminalTool.name),
            Tool(name=FileEditorTool.name),
            Tool(name=TaskTrackerTool.name),
        ],
    )

    workspace = Path.cwd()
    return Conversation(agent=agent, workspace=str(workspace))


@app.post("/run", response_model=RunResponse)
def run_prompt(request: RunRequest) -> RunResponse:
    try:
        conversation = create_conversation()
        conversation.send_message(request.prompt)
        conversation.run()
        return RunResponse(
            status="completed",
            message="The OpenHands conversation completed successfully.",
            workspace=str(Path.cwd()),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


def main() -> None:
    host = os.getenv("OPENHANDS_HOST", "0.0.0.0")
    port = int(os.getenv("OPENHANDS_PORT", "8001"))
    uvicorn_run("agent_service:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
