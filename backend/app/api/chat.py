import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.chat_agent import ChatAgent

router = APIRouter(prefix="/chat", tags=["Chat API"])


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1)


def get_agent() -> ChatAgent:
    return ChatAgent()


@router.post("/stream")
def chat_stream(
    payload: ChatRequest,
    agent: ChatAgent = Depends(get_agent),
) -> StreamingResponse:
    """Server-Sent Events: streams the assistant reply token-by-token, plus
    tool_use / tool_result events as the agent looks up Upbit market data."""
    history = [{"role": m.role, "content": m.content} for m in payload.messages]

    def event_stream():
        for ev in agent.stream(history):
            yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
