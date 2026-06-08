import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import chat, factsheet, models
from app.config.database import engine, Base


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

Base.metadata.create_all(engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services.data_initializer import initialize_data
    await initialize_data()
    yield

app = FastAPI(title="Upcycling RAG Prototype - FastAPI Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8080", "http://127.0.0.1:3000", "http://127.0.0.1:8080"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(factsheet.router)
app.include_router(models.router)

@app.get("/")
def read_root():
    return {"message": "Upcycling RAG Prototype FastAPI Backend"}
