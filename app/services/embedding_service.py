import httpx
from typing import List
from app.config.config import settings


class EmbeddingService:
    def __init__(self):
        self.base_url = settings.ollama_url
        self.model = "nomic-embed-text-v2-moe"

    async def create_embedding(self, text: str) -> List[float]:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/embed",
                json={
                    "model": self.model,
                    "input": [text]
                },
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            return data["embeddings"][0]


embedding_service = EmbeddingService()
