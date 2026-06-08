import logging
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator
from typing import List, Optional, AsyncIterator
from datetime import datetime
import json
from app.config.database import get_db
from app.services.rag_service import rag_service

logger = logging.getLogger(__name__)
router = APIRouter()


class Message(BaseModel):
    role: str
    content: str

    @field_validator('role')
    @classmethod
    def validate_role(cls, value):
        allowed_roles = ['user', 'assistant', 'system']
        if value not in allowed_roles:
            raise ValueError(f"role must be one of {allowed_roles}")
        return value

    @field_validator('content')
    @classmethod
    def validate_content(cls, value):
        if not value or not value.strip():
            raise ValueError("content cannot be empty")
        if len(value) > 10000:
            raise ValueError("content cannot exceed 10000 characters")
        return value.strip()


class ChatCompletionRequest(BaseModel):
    messages: List[Message]
    stream: Optional[bool] = False
    user: Optional[str] = "anonymous"
    model: Optional[str] = "rag"

    @field_validator('messages')
    @classmethod
    def validate_messages(cls, value):
        if not value or len(value) == 0:
            raise ValueError("messages cannot be empty")
        if len(value) > 100:
            raise ValueError("Too many messages (max 100)")
        return value

    @field_validator('model')
    @classmethod
    def validate_model(cls, value):
        allowed_models = ['rag', 'no-rag']
        if value not in allowed_models:
            raise ValueError(f"model must be one of {allowed_models}")
        return value

    @field_validator('user')
    @classmethod
    def validate_user(cls, value):
        if not value or not value.strip():
            raise ValueError("user cannot be empty")
        if len(value) > 100:
            raise ValueError("user identifier too long (max 100 characters)")
        return value.strip()


@router.post("/v1/chat/completions", response_model=None)
async def chat_completions(
        request: ChatCompletionRequest,
        db: Session = Depends(get_db)
):
    user_message = request.messages[-1].content if request.messages else ""
    use_rag = request.model == "rag"

    if request.stream:
        return StreamingResponse(
            stream_chat_response(user_message, request.user, db, use_rag),
            media_type="text/event-stream"
        )
    else:
        response_text = await rag_service.ask(user_message, request.user, db, use_rag=use_rag)

        return {
            "id": f"chatcmpl-{int(datetime.now().timestamp())}",
            "object": "chat.completion",
            "created": int(datetime.now().timestamp()),
            "model": request.model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response_text
                    },
                    "finish_reason": "stop"
                }
            ]
        }


async def stream_chat_response(
        user_message: str,
        user_id: str,
        db: Session,
        use_rag: bool = True
) -> AsyncIterator[str]:
    try:
        timestamp = int(datetime.now().timestamp())

        stream = rag_service.ask_stream(user_message, user_id, db, use_rag=use_rag)

        async for chunk in stream:
            chunk_data = {
                "id": f"chatcmpl-{timestamp}",
                "object": "chat.completion.chunk",
                "created": timestamp,
                "model": "rag" if use_rag else "no-rag",
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "content": chunk
                        },
                        "finish_reason": None
                    }
                ]
            }
            yield f"data: {json.dumps(chunk_data)}\n\n"

        final_chunk = {
            "id": f"chatcmpl-{timestamp}",
            "object": "chat.completion.chunk",
            "created": timestamp,
            "model": "rag" if use_rag else "no-rag",
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop"
                }
            ]
        }
        yield f"data: {json.dumps(final_chunk)}\n\n"
        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error("Streaming error (rag=%s): %s", use_rag, e, exc_info=True)
        error_data = {
            "error": {
                "message": str(e),
                "type": "internal_error"
            }
        }
        yield f"data: {json.dumps(error_data)}\n\n"
