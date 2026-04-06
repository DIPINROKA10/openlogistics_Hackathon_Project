# OpenLogistics - AI Supply Chain Game

🏭 AI Supply Chain Optimization Environment

## 🎮 Overview

OpenLogistics is an AI-powered logistics simulation game where agents learn to optimize delivery operations.

## 🚀 Quick Start

```bash
# Play the game
python game.py

# Run API server
uvicorn app.main:app --host 0.0.0.0 --port 7860
```

## 📋 Tasks

| Task | Difficulty | Description |
|------|------------|-------------|
| `easy_delivery` | Easy | Basic single delivery |
| `medium_optimization` | Medium | Multi-order with blocked routes |
| `hard_crisis` | Hard | Crisis management with dynamics |

## 🛠️ API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/reset` | POST | Initialize environment |
| `/api/v1/step` | POST | Execute action |
| `/api/v1/state` | GET | Get current state |
| `/api/v1/grade` | GET | Get score |

## 📁 Project Structure

```
openlogistics/
├── app/                  # FastAPI backend
├── game.py              # Console game
├── inference/           # LLM agent
└── tests/              # Tests
```

## 📜 License

MIT License
