from psycopg.rows import DictRow, dict_row
from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool
from neo4j import AsyncGraphDatabase

from app.configs.settings.settings import get_settings


settings = get_settings()

langgraph_connection_pool: AsyncConnectionPool[AsyncConnection[DictRow]] = AsyncConnectionPool(
    conninfo=settings.langgraph_postgres_url,
    # max_size=20,
    kwargs={
        "autocommit": True,
        "row_factory": dict_row,
    },
    open=False
)



neo4j_driver = AsyncGraphDatabase.driver(
    settings.neo4j_uri,
    auth=(settings.neo4j_username, settings.neo4j_password)
)