# Search Knowledge Base

Semantic search API over local documents using AWS Bedrock embeddings and PostgreSQL with pgvector.
The problem targetted is to locate a trainning video based on semantic search. We watch trainning video but
later forgets which trainning video has the details.For Ex. if I want to search which training video has how to setup mac for python3, I can search among a vector database of transcripts and .md files attached to the video.
The more important use case is when the vector database is created from a video file. For Ex. a lecture delivered by a teacher in school, a court case discussed by lawyer or politician statement done 50 years ago. We can convert video into transcript and create vector from it.

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

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | — | PostgreSQL connection string |
| `DEFAULT_AWS_REGION` | `ap-southeast-2` | AWS region for Bedrock |
| `BEDROCK_MODEL_ID` | `amazon.nova-lite-v1:0` | Bedrock LLM model |
| `BEDROCK_EMBED_MODEL_ID` | `amazon.titan-embed-text-v2:0` | Bedrock embedding model |
| `CORS_ORIGINS` | `http://localhost:3000` | Allowed CORS origins (comma-separated) |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Root — returns API info |
| `GET` | `/health` | Health check |
| `GET` | `/create_vector` | Load documents, generate embeddings, store in PostgreSQL |

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
