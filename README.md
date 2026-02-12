# Search Knowledge Base

Semantic search API over local documents using AWS Bedrock embeddings and PostgreSQL with pgvector.

The problem targeted is to locate a training video based on semantic search. We watch training videos but later forget which one has the details. For example, if I want to search which training video covers how to setup Mac for Python 3, I can search among a vector database of transcripts and `.md` files attached to the video.

The more important use case is when the vector database is created from a video file — a lecture delivered by a teacher in school, a court case discussed by a lawyer, or a politician's statement from 50 years ago. We can convert video into transcript and create vectors from it.

## Tech Stack

- **FastAPI** — REST API framework
- **AWS Bedrock** — LLM inference (`amazon.nova-lite-v1:0`) and embeddings (`amazon.titan-embed-text-v2:0`)
- **PostgreSQL + pgvector** — Vector storage and similarity search
- **LangChain** — Document loading and text splitting

## Prerequisites

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) (package manager)
- Docker (for PostgreSQL)
- AWS credentials with Bedrock model access enabled

## Getting Started

```bash
# Install dependencies
uv sync

# Copy env file and fill in values
cp .env.example .env

# Start the server
uv run uvicorn backend.app.server:app --reload
```

## Database Setup

Start PostgreSQL with pgvector:

```bash
docker run --name postgres \
    -e POSTGRES_PASSWORD=your_password \
    -p 5432:5432 \
    -d pgvector/pgvector:pg16
```

Create the schema:

```sql
CREATE EXTENSION vector;

CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(500),
    source_url TEXT,
    doc_type VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER,
    content TEXT NOT NULL,
    embedding vector(1024),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON chunks (document_id);
```

## Environment Variables

| Variable                 | Default                        | Description                            |
| ------------------------ | ------------------------------ | -------------------------------------- |
| `DATABASE_URL`           | —                              | PostgreSQL connection string           |
| `DEFAULT_AWS_REGION`     | `ap-southeast-2`               | AWS region for Bedrock                 |
| `BEDROCK_MODEL_ID`       | `amazon.nova-lite-v1:0`        | Bedrock LLM model                      |
| `BEDROCK_EMBED_MODEL_ID` | `amazon.titan-embed-text-v2:0` | Bedrock embedding model                |
| `CORS_ORIGINS`           | `http://localhost:3000`        | Allowed CORS origins (comma-separated) |

## API Endpoints

| Method | Path             | Description                                              |
| ------ | ---------------- | -------------------------------------------------------- |
| `GET`  | `/`              | Root — returns API info                                  |
| `GET`  | `/health`        | Health check                                             |
| `GET`  | `/create_vector` | Load documents, generate embeddings, store in PostgreSQL |
| `POST` | `/search`        | Semantic search — takes a question, returns LLM answer with sources |

## Usage Example

```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"question": "clone a repository in linux"}'
```

Response:

```json
{
  "answer": "# Clone a Repository in Linux\n\nTo clone a repository...",
  "filenames": [
    "documents/udemy/ai-engineering/SETUP-git-linux.md"
  ],
  "sources": [
    {
      "filename": "documents/udemy/ai-engineering/SETUP-git-linux.md",
      "similarity": 0.3586,
      "excerpt": "# Setting Up Git on Linux..."
    }
  ]
}
```

## Future Enhancements

### Authentication with Clerk

Integrate [Clerk](https://clerk.com/) for user authentication and multi-tenancy:

- Sign up / sign in with email, Google, or GitHub
- Protect API endpoints with JWT verification middleware
- Per-user knowledge bases — scope documents and chunks to the authenticated user
- User dashboard to manage uploaded documents and search history

### Payments with Stripe

Add [Stripe](https://stripe.com/) to turn this into a SaaS product:

- Free tier with limited searches per month and document upload cap
- Pro tier with unlimited searches, larger document storage, and priority embedding processing
- Stripe Checkout for subscription management
- Webhook integration to activate/deactivate features based on subscription status
- Usage-based billing option for high-volume API consumers


## Frontend

The UI is a Next.js app in `frontend/search-knowledge-base-app/`.

```bash
cd frontend/search-knowledge-base-app && npm run dev
```

Open `http://localhost:3000` — it redirects to `/home` where you can search the knowledge base.
