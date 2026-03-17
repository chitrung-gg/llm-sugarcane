import httpx
from loguru import logger

from app.configs.settings.settings import get_settings


TIMEOUT = 120
async def call_backend(method: str, endpoint: str, params=None, json_data=None) -> dict:
    settings = get_settings()

    # Grab URL
    base_url = getattr(settings, "genome_backend_api_url", "http://localhost:8000").rstrip("/")
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
        return {"error": str(e), "details": e.response.text, "status": "failed"}
    except Exception as e:
        logger.error(f"Backend API Call Failed: {url} - {str(e)}")
        return {"error": str(e), "status": "failed"}
