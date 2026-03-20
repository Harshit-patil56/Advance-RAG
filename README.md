# Advance RAG

Advance RAG is a domain-aware RAG system for document ingestion, retrieval, and structured Q&A across finance, law, and global domains.

## What it does
- Session-based querying for three domains: finance, law, global
- File ingestion pipeline:
  - finance: CSV
  - law: PDF, TXT
  - global: CSV, PDF, TXT
- Retrieval + generation pipeline with strict structured output:
  - insights
  - warnings
  - recommendations
  - data
- Finance analytics generation (category totals, monthly trends, chart payloads)
- Chart filtering by query constraints (top N and amount thresholds)
- Conversation history and periodic memory summaries
- Folder CRUD and document exploration tools (`ls`, `tree`, `glob`, `gp`, `read`)
- Runtime model settings API and UI modal (enable/disable providers, model names, temperature, token limits, timeout)

## Tech stack

### Backend
- FastAPI
- Uvicorn
- Supabase (database + storage)
- Qdrant
- HuggingFace embeddings
- Gemini + Groq (router fallback)
- pandas, PyMuPDF, pdfplumber

### Frontend
- Next.js 16 (App Router)
- React 19 + TypeScript
- Axios
- Recharts
- Framer Motion
- Lucide React
- Better Auth + better-sqlite3

### Testing
- pytest
- pytest-asyncio

## Project structure
```text
backend/
  core/         database, qdrant, schemas, exceptions, runtime LLM settings
  migrations/   SQL migrations for schema evolution
  pipelines/    ingestion, retrieval, generation, memory, finance logic
  routers/      API route handlers
  tests/        backend tests

frontend/
  src/app/      pages and route handlers
  src/components/
  src/lib/      API and auth clients
```

## Requirements
- Python 3.10+
- Node.js 18+
- Supabase project
- Qdrant instance
- API keys for HuggingFace, Gemini, Groq

## Setup

### 1. Backend
```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

Create `backend/.env` from `backend/.env.example` and provide values.

Required variables:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `QDRANT_URL`
- `QDRANT_API_KEY`
- `HUGGINGFACE_API_TOKEN`
- `GEMINI_API_KEY`
- `GROQ_API_KEY`

Optional variables (defaults exist in code):
- `HUGGINGFACE_MODEL`
- `GEMINI_MODEL`
- `GROQ_MODEL`
- `ALLOWED_ORIGINS`
- `APP_VERSION`
- `MAX_FILE_SIZE_MB`
- `MAX_QUERY_CHARS`
- `RETRIEVAL_TOP_K`
- `RETRIEVAL_SCORE_THRESHOLD`
- `EMBEDDING_BATCH_SIZE`
- `MAX_SUMMARY_TOKENS`
- `LLM_TIMEOUT_SECONDS`

Apply migrations in Supabase SQL editor (in order):
1. `backend/migrations/001_initial_schema.sql`
2. `backend/migrations/002_folders_and_exploration.sql`
3. `backend/migrations/003_session_name.sql`
4. `backend/migrations/004_allow_global_domain.sql`

Start backend:
```bash
cd backend
.venv\Scripts\activate
uvicorn main:app --reload
```

### 2. Frontend
```bash
cd frontend
npm install
npm run dev
```

Frontend env vars used by code:
- `NEXT_PUBLIC_API_URL` (default: `http://localhost:8000`)
- `NEXT_PUBLIC_AUTH_BASE_URL` (default: `http://localhost:3000`)

## API endpoints

Base prefix: `/api/v1`

| Method | Endpoint | Description |
|---|---|---|
| POST | `/sessions` | Create session |
| PATCH | `/sessions/{session_id}` | Rename session |
| GET | `/sessions?user_id=...` | List user sessions |
| GET | `/sessions/{session_id}/files` | List files in session |
| DELETE | `/sessions/{session_id}` | Soft-delete session |
| POST | `/ingest` | Upload and index file |
| GET | `/files/{file_id}/chart` | Get chart data |
| DELETE | `/files/{file_id}` | Delete file |
| POST | `/query` | Submit query |
| GET | `/sessions/{session_id}/history` | Get paginated history |
| GET | `/sessions/{session_id}/memory` | Get memory summary |
| GET | `/health` | Liveness check |
| HEAD | `/health` | Uptime check |
| GET | `/health/deep` | Dependency health check |
| GET | `/settings/llm` | Get runtime LLM settings |
| PUT | `/settings/llm` | Update runtime LLM settings |
| POST | `/folders` | Create folder |
| GET | `/folders` | List folders |
| GET | `/folders/{folder_id}` | Get folder |
| PATCH | `/folders/{folder_id}` | Update folder |
| DELETE | `/folders/{folder_id}` | Delete folder |
| POST | `/folders/{folder_id}/share` | Make folder shared |
| POST | `/folders/{folder_id}/private` | Make folder private |
| GET | `/tools/ls` | List folder contents |
| GET | `/tools/tree` | Folder tree |
| GET | `/tools/glob` | Pattern match |
| GET | `/tools/gp` | Grep search |
| GET | `/tools/read` | Read document content |

Frontend auth handler route:
- `/api/auth/*`

## Usage
1. Open frontend at `http://localhost:3000`.
2. Sign up or log in.
3. Create a session in the target domain.
4. Upload a compatible file.
5. Submit queries and review structured responses.
6. Use chart panel for finance responses.
7. Use Settings modal to adjust runtime model controls.

## Deployment
- No deployment manifest is included in this repository.
- Uptime checks can use `HEAD /api/v1/health`.

## License
No license file is currently defined in this repository.
