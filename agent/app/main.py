from contextlib import asynccontextmanager

from loguru import logger

from app.configs.loggings.loggings import init_opentelemetry, setup_logging
from app.configs.storage.databases import genome_connection_pool, langgraph_connection_pool

from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# Start up early to intercept FastAPI logging
setup_logging()
init_opentelemetry()

from fastapi import FastAPI


from app.core.app_container import get_container
from app.api.v1 import chat_endpoint, ingestion_endpoint


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize all services on startup, clean up on shutdown."""

    logger.info("🔌 Opening Genome PostgreSQL connection pool...")
    await genome_connection_pool.open()
    
    logger.info("🔌 Opening LangGraph PostgreSQL connection pool...")
    await langgraph_connection_pool.open()

    # logger.info("🔌 Opening RustFS client ...")
    # await rustfs_client.__aenter__()

    logger.info("⚙️ Initializing app container and compiling graph...")
    await get_container().initialize()
    yield
    # teardown if needed (e.g. close DB connections)

    logger.info("🛑 Shutting down server...")

    logger.info("🔌 Closing Genome PostgreSQL connection pool...")
    await genome_connection_pool.close()

    logger.info("🔌 Closing LangGraph PostgreSQL connection pool...")
    await langgraph_connection_pool.close()

    # logger.info("🔌 Closing RustFS client ...")
    # await rustfs_client.__aexit__(None, None, None)


app = FastAPI(
    title="Sugarcane Genome Agent",
    lifespan=lifespan)

FastAPIInstrumentor.instrument_app(app)

app.include_router(chat_endpoint.router, prefix="/api/v1/agent")
app.include_router(ingestion_endpoint.router, prefix="/api/v1/ingest")

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