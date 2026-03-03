from contextlib import asynccontextmanager

from fastapi import FastAPI

from agent.app.core.app_container import get_container
from app.api.v1 import chat_endpoint



@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize all services on startup, clean up on shutdown."""
    get_container().initialize()
    yield
    # teardown if needed (e.g. close DB connections)
    print("🛑 Shutting down...")

app = FastAPI(
    title="Sugarcane Genome Agent",
    lifespan=lifespan)

app.include_router(chat_endpoint.router, prefix="/api/v1")

@app.get("/")
def root():
    return {"message": "Sugarcane Genome Agent is running!"}

