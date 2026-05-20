import httpx
from loguru import logger

from app.configs.settings.settings import get_settings


TIMEOUT = 60

async def call_genome_backend(method: str, endpoint: str, params=None, json_data=None) -> dict:
    settings = get_settings()

    # Grab URL
    base_url = settings.GENOME_BACKEND_API_URL.rstrip("/")
    endpoint = endpoint if endpoint.startswith("/") else f"/{endpoint}"
    url = f"{base_url}{endpoint}"

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.request(
                method=method,
                url=url,
                params=params,
                json=json_data
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP Error {e.response.status_code} for {url}: {e.response.text}")
        raise RuntimeError(
            f"Genome Backend HTTP {e.response.status_code}: {e.response.text}"
        )
    except httpx.RequestError as e:
        logger.error(f"Request failed for {url}: {str(e)}")
        raise RuntimeError(f"Failed to connect to Genome Backend: {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error for {url}: {str(e)}")
        raise
