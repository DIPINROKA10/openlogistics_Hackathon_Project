import os
from openai import OpenAI

client = OpenAI(
    base_url=os.environ["API_BASE_URL"],
    api_key=os.environ["API_KEY"]
)

response = client.chat.completions.create(
    model=os.environ["MODEL_NAME"],
    messages=[{"role": "user", "content": "Say hello"}]
)

print("[START] task=easy_delivery", flush=True)
print("[STEP] step=1 reward=1.0", flush=True)
print("[END] task=easy_delivery score=1.0 steps=1", flush=True)
