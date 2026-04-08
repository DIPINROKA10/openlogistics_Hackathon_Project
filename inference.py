import os
from openai import OpenAI

# Required environment variables
API_BASE_URL = os.getenv("API_BASE_URL", "https://dipinroka-openlogistics-demo.hf.space")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
HF_TOKEN = os.getenv("HF_TOKEN")  # No default for HF_TOKEN!

# optional
LOCAL_IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME")

client = OpenAI(
    base_url=API_BASE_URL,
    api_key=HF_TOKEN or "dummy"
)

def predict(inputs: dict) -> dict:
    print("START")
    
    print(f"STEP: Running prediction with model {MODEL_NAME}")
    
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "user", "content": str(inputs)}
        ]
    )
    
    result = response.choices[0].message.content
    print(f"STEP: Got result: {result}")
    
    print("END")
    
    return {"result": result}
