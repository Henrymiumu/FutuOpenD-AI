# Futu Market AI

> **練習專案**：本專案僅供學習與個人練習使用，非正式產品。分析結果僅供參考，**不構成投資建議**。

透過本機 **Futu OpenD** 取得股票報價與 K 線，再交給 **AI（Ollama / OpenAI / Gemini 等）** 產出簡易市場分析。前端為 Vue 3，後端為 FastAPI。

## 用途

- 連接本機 Futu OpenD 取得行情快照、K 線
- 將市場資料送給本地或雲端 LLM 做文字分析
- 練習：OpenD API、FastAPI、Vue、多 LLM 串接

## 前置條件

1. Python 3.10+
2. Node.js 18+
3. [Futu OpenD](https://www.futunn.com/download/OpenAPI) 已安裝並登入
4. （可選）[Ollama](https://ollama.com) 或其他雲端 AI API Key

## 部署 / 本機啟動

### 1. 後端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python run.py
```

API 文件：http://127.0.0.1:8000/docs

### 2. 前端（另開終端機）

```powershell
cd frontend
npm install
npm run dev
```

瀏覽器開啟：http://127.0.0.1:5173

### 使用前

1. 確認 OpenD 已啟動（預設 `127.0.0.1:11111`）
2. 在網頁選擇 AI 供應商並填入 Key（Ollama 通常不需 Key）
3. 輸入代碼，例如：`HK.00700, US.AAPL`

## 目錄

```
backend/    FastAPI + futu-api + LLM
frontend/   Vue 3 + Vite
scripts/    Windows 啟動腳本（可選）
```
