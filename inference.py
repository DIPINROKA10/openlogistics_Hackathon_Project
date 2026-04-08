import os
import requests

API_BASE_URL = os.getenv("API_BASE_URL", "https://dipinroka10-openlogistics-d.hf.space")
MODEL_NAME = os.getenv("MODEL_NAME", "default")
HF_TOKEN = os.getenv("HF_TOKEN", "")

def predict(inputs: dict) -> dict:
    headers = {"Content-Type": "application/json"}
    if HF_TOKEN:
        headers["Authorization"] = f"Bearer {HF_TOKEN}"
    
    response = requests.post(
        f"{API_BASE_URL}/predict",
        json=inputs,
        headers=headers
    )
    return response.json()
