# FutuOpenD_AI

> **Practice project only.** For learning and personal practice.

Fetch stock quotes and K-line data via local **Futu OpenD**, then send them to an **AI** (Ollama / OpenAI / Gemini, etc.) for a simple market summary. Frontend: Vue 3. Backend: FastAPI.

## Purpose

- Connect to local Futu OpenD for market snapshots and K-lines
- Pass market data to a local or cloud LLM for text analysis
- Practice: OpenD API, FastAPI, Vue, and multi-LLM integration

## Requirements

1. Python 3.10+
2. Node.js 18+
3. [Futu OpenD](https://www.futunn.com/download/OpenAPI) installed and logged in
4. (Optional) [Ollama](https://ollama.com) or a cloud AI API key

## Setup / Run locally

### 1. Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python run.py
```

API docs: http://127.0.0.1:8000/docs

### 2. GitHub Pages (frontend only)

How it works:

1. The UI is at `https://henrymiumu.github.io/FutuOpenD-AI/`
2. Each visitor still runs **OpenD + backend locally** (`python run.py`)
3. The hosted page calls `http://127.0.0.1:8000`

### Before using

1. Make sure OpenD is running (default `127.0.0.1:11111`)
2. Pick an AI provider in the UI and enter an API key (Ollama usually needs none)
3. Enter codes, e.g. `HK.00700, US.AAPL`


## Layout

```
backend/    FastAPI + futu-api + LLM
frontend/   Vue 3 + Vite
scripts/    Optional Windows start scripts
```
