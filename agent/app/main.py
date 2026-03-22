from contextlib import asynccontextmanager

from loguru import logger

from app.configs.loggings.loggings import setup_logging
from app.configs.storage.databases import langgraph_connection_pool
from app.configs.storage.object_storage import rustfs_client



# Start up early to intercept FastAPI logging
setup_logging()

from fastapi import FastAPI


from app.core.app_container import get_container
from app.api.v1 import chat_endpoint


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize all services on startup, clean up on shutdown."""

    logger.info("🔌 Opening PostgreSQL connection pool...")
    await langgraph_connection_pool.open()
    await rustfs_client.__aenter__()

    logger.info("⚙️ Initializing app container and compiling graph...")
    await get_container().initialize()
    yield
    # teardown if needed (e.g. close DB connections)

    logger.info("🛑 Shutting down server...")
    logger.info("🔌 Closing PostgreSQL connection pool...")
    logger.info("🔌 Closing RustFS client ...")
    await langgraph_connection_pool.close()
    await rustfs_client.__aexit__()


app = FastAPI(
    title="Sugarcane Genome Agent",
    lifespan=lifespan)

app.include_router(chat_endpoint.router, prefix="/api/v1")

@app.get("/")
async def root():
    return {"message": "Sugarcane Genome Agent is running!"}

if __name__ == "__main__":
    import uvicorn
    
    # Run Uvicorn from inside Python. 
    # CRITICAL: log_config=None forces Uvicorn to NOT apply its default formatting!
    uvicorn.run(
        "app.main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True,
        log_config=None 
    )