from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200

def test_tasks_endpoint():
    response = client.get("/api/v1/tasks")
    assert response.status_code == 200
    assert "tasks" in response.json()

def test_environment_flow():
    # Reset
    response = client.post("/api/v1/reset", json={"task_id": "easy_delivery"})
    assert response.status_code == 200
    state = response.json()
    assert state["task_id"] == "easy_delivery"

    # State
    response = client.get("/api/v1/state")
    assert response.status_code == 200
    assert response.json()["task_id"] == "easy_delivery"

    # Step
    response = client.post("/api/v1/step", json={
        "actions": [
            {"type": "wait", "truck_id": "T1"}
        ]
    })
    assert response.status_code == 200
    assert response.json()["done"] is False
    
    # Grade
    response = client.get("/api/v1/grade")
    assert response.status_code == 200
    assert "score" in response.json()

def test_episode_reset():
    response = client.post("/api/v1/episode/reset")
    assert response.status_code == 200
    assert response.json()["message"] == "Environment reset successful"
