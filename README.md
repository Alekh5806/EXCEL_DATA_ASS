# Excel Data Intelligence Chatbot

This project has two parts:

1. A Django API that imports Excel rows into PostgreSQL and answers chat requests.
2. A Vite frontend that uploads the spreadsheet and sends chat questions to the API.

## What the app does

The intended flow is:

1. Upload the Excel workbook into the database.
2. Ask a natural-language question.
3. The LLM generates safe SQL.
4. The SQL is executed against PostgreSQL.
5. The SQL result is sent back to the LLM for a concise answer.

The backend already supports this flow through the chat endpoint.

The SQL prompt now also includes a semantic layer for the ProcessData table, so the model sees column meanings, synonyms, and common question patterns before generating SQL.

## Local Setup

### 1) Create and activate the virtual environment

Use the existing `venv` folder if it is already present:

```powershell
Set-Location 'D:\Projects\Data analytic\EXCEL_DATA_ASS'
.\venv\Scripts\Activate.ps1
```

If the virtual environment does not exist yet, create it first, then install dependencies.

### 2) Install Python dependencies

```powershell
pip install -r requirements.txt
```

### 3) Create PostgreSQL database

Create a local database named `excel_data_ass`, then set `DATABASE_URL` in your `.env` file.

Example:

```env
DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/excel_data_ass
```

If you do not set `DATABASE_URL`, Django falls back to SQLite, but PostgreSQL is the intended setup for this app.

### 4) Copy the environment example

Use `.env.example` as the starting point for `.env`.

Important values for local development:

```env
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
VITE_API_BASE_URL=http://127.0.0.1:8000
CORS_ALLOWED_ORIGINS=http://127.0.0.1:5173,http://localhost:5173
CSRF_TRUSTED_ORIGINS=http://127.0.0.1:5173,http://localhost:5173
```

### 5) Run migrations

```powershell
python manage.py migrate
```

### 6) Create a sample Excel workbook

This repo includes a workbook generator that matches the importer layout:

```powershell
python manage.py create_sample_excel --output sample_process_data.xlsx
```

The generated file is useful for testing the upload flow immediately.

### 7) Start the Django API

```powershell
python manage.py runserver 127.0.0.1:8000
```

### 8) Start the frontend

```powershell
Set-Location 'D:\Projects\Data analytic\EXCEL_DATA_ASS\frontend'
npm install
npm run dev
```

Open `http://127.0.0.1:5173` in the browser.

## Using the app

1. Upload `sample_process_data.xlsx` or your own `.xlsx` file.
2. Ask a question like:
   - `What was the highest temperature on April 8?`
   - `Show temperature trend on April 8`
   - `Compare temperature April 8 and April 9`
3. The backend will generate SQL, run it, and return a short answer.

## Backend checks

Run the backend test suite with:

```powershell
python manage.py test data_app.tests
```

## Notes

- The chat flow uses LangGraph when `OPENAI_API_KEY` is set.
- Start with `OPENAI_MODEL=gpt-4o-mini` for lower-cost API usage; your ChatGPT subscription does not automatically provide API quota.
- If the key is missing, the app falls back to the existing local SQL/heuristic chat path.
- The frontend API URL is configurable through `VITE_API_BASE_URL`.

## Using Ollama Instead Of OpenAI

You can use Ollama as the LLM provider without an OpenAI API key.

Example local `.env` values:

```env
LLM_BASE_URL=http://127.0.0.1:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=qwen2.5-coder:14b
OPENAI_API_KEY=
OPENAI_MODEL=
```

Then make sure Ollama is running and the model is available:

```powershell
ollama run qwen2.5-coder:14b
```

The backend will use the OpenAI-compatible Ollama endpoint for both SQL generation and final answer generation.