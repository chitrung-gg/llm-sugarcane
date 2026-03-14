from contextlib import asynccontextmanager


from app.configs.logging.logging import setup_logging

# Start up early to intercept FastAPI logging
setup_logging()

from fastapi import FastAPI


from app.core.app_container import get_container
from app.api.v1 import chat_endpoint


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize all services on startup, clean up on shutdown."""
    get_container().initialize()
    yield
    # teardown if needed (e.g. close DB connections)

app = FastAPI(
    title="Sugarcane Genome Agent",
    lifespan=lifespan)

app.include_router(chat_endpoint.router, prefix="/api/v1")

@app.get("/")
def root():
    return {"message": "Sugarcane Genome Agent is running!"}

if __name__ == "__main__":
    import uvicorn
    
    # Run Uvicorn from inside Python. 
    # CRITICAL: log_config=None forces Uvicorn to NOT apply its default formatting!
    uvicorn.run(
        "app.main:app", 
        host="127.0.0.1", 
        port=8000, 
        reload=True,
        log_config=None 
    )