# OpenLogistics - AI Supply Chain Optimization Environment

AI Supply Chain Optimization Environment built on OpenEnv standard for evaluating AI agents' capabilities in multi-step planning, spatial reasoning, and constraint optimization.

## 🚚 Overview

OpenLogistics transforms AI evaluation from text-based tasks to real-world decision-making simulation, testing an AI's ability to plan, adapt, optimize, and execute like a real operations manager.

## 📋 Tasks

| Task | Difficulty | Description |
|------|------------|-------------|
| `easy_delivery` | Easy | Basic single delivery between two warehouses |
| `medium_optimization` | Medium | Multi-order optimization with route blocking |
| `hard_crisis` | Hard | Crisis management with dynamic events |

## 🛠️ Installation

```bash
pip install -r requirements.txt
```

## 🚀 Quick Start

### Run API Server

```bash
cd app
uvicorn main:app --host 0.0.0.0 --port 7860
```

### Run Inference

```bash
python -m inference.agent --task easy_delivery
```

## 📡 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/reset` | POST | Initialize environment |
| `/api/v1/state` | GET | Get current state |
| `/api/v1/step` | POST | Execute action |
| `/api/v1/grade` | GET | Get final score |
| `/api/v1/tasks` | GET | List tasks |
| `/api/v1/health` | GET | Health check |

## 🎮 Usage Example

```python
from app.environment.core import OpenLogisticsEnv
from app.models.models import Action, SingleAction, ActionType

env = OpenLogisticsEnv()
state = env.reset("easy_delivery")

action = Action(actions=[
    SingleAction(type=ActionType.LOAD, truck_id="T1", target="W1", items={"itemA": 30}),
    SingleAction(type=ActionType.MOVE, truck_id="T1", target="W2"),
    SingleAction(type=ActionType.DELIVER, truck_id="T1", order_id="O1")
])

result = env.step(action)
print(f"Reward: {result.reward}, Done: {result.done}")

score = env.grade()
print(f"Score: {score['score']}")
```

## 🐳 Docker

```bash
docker build -t openlogistics .
docker run -p 7860:7860 openlogistics
```

## 📊 Scoring

Score range: 0.0 - 1.0

- **0.0 - 0.3**: Poor
- **0.3 - 0.5**: Below Average
- **0.5 - 0.7**: Average
- **0.7 - 0.9**: Good
- **0.9 - 1.0**: Excellent

## 📁 Project Structure

```
openlogistics/
├── app/
│   ├── main.py              # FastAPI app
│   ├── environment/         # Environment engine
│   ├── tasks/               # Task configurations
│   ├── models/              # Data models
│   └── api/                 # API routes
├── inference/               # LLM agent
├── tests/                   # Tests
├── requirements.txt
└── Dockerfile
```

## 📜 License

MIT License
