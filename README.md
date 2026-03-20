# Advance RAG

## Overview
Advance RAG is a full-stack, domain-aware RAG application for document analysis across three domains:
- Finance
- Law
- Global

It provides:
- File ingestion and indexing
- Session-based chat querying
- Structured LLM responses
- Finance chart generation and filtering
- Folder-based document organization and exploration tools
- Runtime LLM settings control

The project combines a FastAPI backend with a Next.js frontend and uses Supabase and Qdrant as core data infrastructure.

## What This Project Does
The system solves a common multi-document analysis problem:
- ingest heterogeneous files (CSV, PDF, TXT)
- index content into vector storage with domain separation
- answer user queries with retrieval + generation
- keep conversation history and periodic summaries
- expose charts and structured outputs for financial analysis

## Features
- Domain-aware sessions: finance, law, global
- Domain-specific ingestion rules
  - Finance: CSV
  - Law: PDF/TXT
  - Global: CSV/PDF/TXT
- Qdrant vector retrieval with session/file filtering
- LLM routing with fallback
  - Gemini primary
  - Groq fallback
- Structured response format
  - insights
  - warnings
  - recommendations
  - data payload
- Finance analytics
  - category totals
  - monthly trends
  - top categories
  - summary statistics
  - bar/line/pie chart data
- Query-time chart filtering
  - top-N constraints
  - amount threshold constraints (over/under/between)
- Session history and memory summary endpoints
- Folder management and exploration tools (ls/tree/glob/grep/read)
- Runtime model settings endpoint and UI modal
  - provider enable/disable
  - model names
  - temperatures
  - top_p
  - token limits
  - timeout
- Auth-enabled frontend (Better Auth)
- Health checks
  - GET /api/v1/health
  - HEAD /api/v1/health
  - GET /api/v1/health/deep

## Tech Stack
### Backend
- FastAPI
- Uvicorn
- Pydantic + pydantic-settings
- Supabase (database + storage)
- Qdrant
- HuggingFace embeddings
- Google Generative AI (Gemini)
- Groq
- pandas
- PyMuPDF and pdfplumber

### Frontend
- Next.js (App Router)
- React
- TypeScript
- Axios
- Recharts
- Framer Motion
- Lucide React
- Better Auth
- better-sqlite3

### Testing
- pytest
- pytest-asyncio

## Architecture
High-level backend flow:
1. Ingest
   - Validate domain and file type
   - Upload raw bytes to Supabase Storage
   - Store file metadata in Supabase
   - Parse and normalize content
   - Chunk + embed
   - Upsert embeddings to Qdrant
   - Persist finance chart_data when applicable
2. Query
   - Validate session and optional file ownership
   - Embed query
   - Retrieve chunks from Qdrant and memory context in parallel
   - Build prompt
   - Route LLM call (Gemini then Groq fallback)
   - Validate structured JSON output
   - Enrich finance and law responses deterministically
   - Persist chat messages and trigger periodic summarization
3. Frontend
   - Authenticated session UX
   - Domain/session/file management
   - Chat and chart visualization
   - Runtime settings modal for LLM controls

## Project Structure

- backend
  - main.py: FastAPI app entrypoint
  - config.py: backend configuration from environment
  - core
    - database.py: Supabase wrapper
    - qdrant.py: Qdrant wrapper and collection setup
    - exceptions.py: application errors
    - schemas.py: API schemas
    - runtime_llm_settings.py: in-memory runtime model settings
  - pipelines
    - ingestion: parsing, chunking, embedding, indexing
    - retrieval: vector retrieval and memory fetch
    - generation: prompt building, LLM routing, output validation
    - memory: periodic summarization
    - finance: deterministic financial aggregation and validation
  - routers
    - sessions.py
    - ingest.py
    - query.py
    - history.py
    - health.py
    - folders.py
    - settings.py
  - migrations
    - 001_initial_schema.sql
    - 002_folders_and_exploration.sql
    - 003_session_name.sql
    - 004_allow_global_domain.sql
  - tests

- frontend
  - src/app: pages, route handlers, layout
  - src/components: chat UI, sidebar, charts, settings modal
  - src/lib: API client and auth client

## Getting Started

### Prerequisites
- Python (with venv support)
- Node.js and npm
- Supabase project (database + storage bucket)
- Qdrant instance
- API keys for HuggingFace, Gemini, and Groq

### Installation

1. Clone repository

2. Backend setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

3. Frontend setup

```bash
cd ../frontend
npm install
```

### Environment Setup

#### Backend
Copy backend/.env.example to backend/.env and set values.

Required backend environment variables:
- SUPABASE_URL
- SUPABASE_SERVICE_ROLE_KEY
- QDRANT_URL
- QDRANT_API_KEY
- HUGGINGFACE_API_TOKEN
- GEMINI_API_KEY
- GROQ_API_KEY

Optional backend environment variables (have defaults in code):
- HUGGINGFACE_MODEL
- GEMINI_MODEL
- GROQ_MODEL
- ALLOWED_ORIGINS
- APP_VERSION
- MAX_FILE_SIZE_MB
- MAX_QUERY_CHARS
- RETRIEVAL_TOP_K
- RETRIEVAL_SCORE_THRESHOLD
- EMBEDDING_BATCH_SIZE
- MAX_SUMMARY_TOKENS
- LLM_TIMEOUT_SECONDS

#### Frontend
Frontend environment variables used by code:
- NEXT_PUBLIC_API_URL (default: http://localhost:8000)
- NEXT_PUBLIC_AUTH_BASE_URL (default: http://localhost:3000)

### Database Migrations (Supabase)
Apply SQL migrations in order using Supabase SQL Editor:
1. backend/migrations/001_initial_schema.sql
2. backend/migrations/002_folders_and_exploration.sql
3. backend/migrations/003_session_name.sql
4. backend/migrations/004_allow_global_domain.sql

### Run Locally

Run backend:

```bash
cd backend
.venv\Scripts\activate
uvicorn main:app --reload
```

Run frontend:

```bash
cd frontend
npm run dev
```

Open frontend at http://localhost:3000

Backend docs:
- http://localhost:8000/docs
- http://localhost:8000/redoc

## API Endpoints

Base prefix: /api/v1

### Sessions
- POST /sessions
- PATCH /sessions/{session_id}
- GET /sessions?user_id=...
- GET /sessions/{session_id}/files
- DELETE /sessions/{session_id}

### Ingestion and Files
- POST /ingest
- GET /files/{file_id}/chart
- DELETE /files/{file_id}

### Query
- POST /query

### History and Memory
- GET /sessions/{session_id}/history
- GET /sessions/{session_id}/memory

### Health
- GET /health
- HEAD /health
- GET /health/deep

### Runtime LLM Settings
- GET /settings/llm
- PUT /settings/llm

### Folders and Exploration
- POST /folders
- GET /folders
- GET /folders/{folder_id}
- PATCH /folders/{folder_id}
- DELETE /folders/{folder_id}
- POST /folders/{folder_id}/share
- POST /folders/{folder_id}/private
- GET /tools/ls
- GET /tools/tree
- GET /tools/glob
- GET /tools/gp
- GET /tools/read

### Frontend Auth Route
- /api/auth/* (handled by Better Auth route handler)

## Usage
1. Sign up or log in from frontend auth pages.
2. Create a session in finance, law, or global domain.
3. Upload a compatible file for the selected domain.
4. Submit queries in chat.
5. For finance queries, open chart view when returned.
6. Use sidebar folders/tools for document organization.
7. Open Settings modal to adjust runtime LLM behavior.

## Deployment
Deployment manifests are not included in this repository.

Health endpoint available for uptime checks:
- HEAD /api/v1/health

## Contributing
1. Create a feature branch.
2. Make focused changes.
3. Run tests:

```bash
cd backend
.venv\Scripts\python -m pytest -q
```

4. Open a pull request.

## License
No license file is currently present in this repository.
