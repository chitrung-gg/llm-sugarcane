import os

GENOME_BACKEND_API_URL = os.getenv("GENOME_BACKEND_API_URL", "http://localhost:8080/api/v1")
# Nếu backend yêu cầu API Key
BACKEND_API_KEY = os.getenv("BACKEND_API_KEY", "") 

# Tùy chọn: Hàm helper để gọi API giúp code gọn hơn
import requests

def call_backend(method: str, endpoint: str, params=None, json=None) -> dict:
    url = f"{GENOME_BACKEND_API_URL}{endpoint}"
    headers = {"Authorization": f"Bearer {BACKEND_API_KEY}"} if BACKEND_API_KEY else {}
    
    try:
        response = requests.request(
            method=method, 
            url=url, 
            params=params, 
            json=json, 
            headers=headers,
            timeout=30 # Quan trọng cho các tác vụ gen nặng (BLAST/Synteny)
        )
        response.raise_for_status() # Quăng lỗi nếu API trả về 4xx, 5xx
        return response.json()
    except requests.exceptions.RequestException as e:
        # Bắt lỗi và trả về dạng dictionary để LLM biết tool bị lỗi thay vì làm sập cả Agent
        return {"error": str(e), "status": "failed"}