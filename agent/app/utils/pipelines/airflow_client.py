from datetime import datetime, timezone

import requests
from fastapi import HTTPException
from loguru import logger

from app.configs.settings.settings import get_settings

settings = get_settings()
# 1. The In-Memory Cache
_jwt_cache = {"token": None}

def get_airflow_jwt_token(force_refresh: bool = False) -> str:
    """Authenticates with Airflow 3 to obtain a JWT token, utilizing an in-memory cache."""
    
    # Return the cached token if it exists and we aren't forcing a refresh
    if not force_refresh and _jwt_cache["token"]:
        return _jwt_cache["token"]

    if not settings.AIRFLOW_BASE_URL:
        raise ValueError("AIRFLOW_BASE_URL is not configured in the environment.")
    if not settings.AIRFLOW_API_AUTH_USERNAME:
        raise ValueError("AIRFLOW_API_AUTH_USERNAME is not configured in the environment.")
    if not settings.AIRFLOW_API_AUTH_PASSWORD:
        raise ValueError("AIRFLOW_API_AUTH_PASSWORD is not configured in the environment.")

    auth_url = f"{settings.AIRFLOW_BASE_URL}/auth/token"
    try:
        response = requests.post(
            auth_url,
            json={
                "username": settings.AIRFLOW_API_AUTH_USERNAME,
                "password": settings.AIRFLOW_API_AUTH_PASSWORD.get_secret_value()
            },
            timeout=5
        )
        response.raise_for_status()
        
        # Save the fresh token to our global cache
        new_token = response.json().get("access_token")
        _jwt_cache["token"] = new_token
        
        logger.info("Successfully fetched and cached new Airflow JWT token.")
        return new_token
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Airflow Authentication Failed: {e}")
        raise HTTPException(status_code=503, detail="Workflow engine authentication failed.")


def trigger_airflow_dag(conf_payload: dict, dag_id: str):
    """Uses a cached JWT token to trigger an Airflow DAG dynamically."""
    
    jwt_token = get_airflow_jwt_token()
    trigger_url = f"{settings.AIRFLOW_BASE_URL}/api/v2/dags/{dag_id}/dagRuns"
    
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json"
    }
    now_utc_string = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    try:
        response = requests.post(
            trigger_url,
            headers=headers,
            json={
                "conf": conf_payload,
                "logical_date": now_utc_string
            },
            timeout=5
        )
        
        # 2. The Retry Logic (If the cached token expired)
        if response.status_code == 401:
            logger.warning("Cached Airflow JWT expired. Refreshing token and retrying...")
            
            # Force fetch a new token
            jwt_token = get_airflow_jwt_token(force_refresh=True)
            headers["Authorization"] = f"Bearer {jwt_token}"
            
            # Retry the exact same request once
            response = requests.post(
                trigger_url,
                headers=headers,
                json={
                    "conf": conf_payload,
                    "logical_date": now_utc_string
                },
                timeout=5
            )
            
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to trigger Airflow DAG: {e}")
        
        raise HTTPException(status_code=503, detail="Failed to dispatch job to workflow engine.")
    
def get_airflow_run_status(dag_id: str, dag_run_id: str):
    """Uses the cached JWT token to fetch the status of an Airflow DAG Run."""
    jwt_token = get_airflow_jwt_token()
    
    # Airflow 2/3 REST API endpoint for checking a specific run
    status_url = f"{settings.AIRFLOW_BASE_URL}/api/v2/dags/{dag_id}/dagRuns/{dag_run_id}"
    
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(status_url, headers=headers, timeout=5)
        
        # Retry logic if token expired
        if response.status_code == 401:
            logger.warning("Cached Airflow JWT expired. Refreshing token and retrying...")
            jwt_token = get_airflow_jwt_token(force_refresh=True)
            headers["Authorization"] = f"Bearer {jwt_token}"
            response = requests.get(status_url, headers=headers, timeout=5)
            
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch Airflow status for {dag_run_id}: {e}")
        raise HTTPException(status_code=503, detail="Failed to fetch workflow status.")