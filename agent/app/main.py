from fastapi import FastAPI

from app.api.v1 import chat_endpoint

app = FastAPI(title="Sugarcane Genome Agent")

app.include_router(chat_endpoint.router, prefix="/api/v1")

@app.get("/")
def root():
    return {"message": "Sugarcane Genome Agent is running!"}