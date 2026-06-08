from fastapi import APIRouter
from datetime import datetime

router = APIRouter()


@router.get("/v1/models")
async def list_models():
    timestamp = int(datetime.now().timestamp())
    return {
        "object": "list",
        "data": [
            {
                "id": "rag",
                "object": "model",
                "created": timestamp,
                "owned_by": "upcycling-rag-backend"
            },
            {
                "id": "no-rag",
                "object": "model",
                "created": timestamp,
                "owned_by": "upcycling-rag-backend"
            }
        ]
    }
