# Search Knowledge Base

Semantic search over documents using AWS Bedrock embeddings, PostgreSQL with pgvector, and RAG-powered answers.

The problem targeted is to locate a training video based on semantic search. We watch training videos but later forget which one has the details. For example, if I want to search which training video covers how to setup Mac for Python 3, I can search among a vector database of transcripts and `.md` files attached to the video.

The more important use case is when the vector database is created from a video file — a lecture delivered by a teacher in school, a court case discussed by a lawyer, or a politician's statement from 50 years ago. We can convert video into transcript and create vectors from it.

As of now, only one document related to setup git on linux is uploaded for RAG. To test short-term and long-term memory, search once for "git" and note the similarity percentage. Then close the tab, reopen, and search for "linux". This time the LLM will have both "git" and "linux" in context from conversation history, giving a better result.

## Features

- Semantic search over markdown documents using vector embeddings
- RAG (Retrieval-Augmented Generation) powered answers via Amazon Bedrock
- Short-term memory using Redis — conversation context within a session
- Long-term memory using PostgreSQL — past conversations persisted on session end
- Session management — auto-generated per browser tab, flushed on close
- Document chunking with LangChain text splitters
- Vector similarity search using PostgreSQL with pgvector
- Documents stored in S3 — downloaded and vectorized on demand
- Database migrations managed by Alembic (auto-run on Lambda cold start)
- REST API with daily request quota and API key authentication
- CloudFront CDN serving frontend (S3) and API (API Gateway)
- Input validation (max 1000 characters) on both backend and frontend
- Lambda deployment packages uploaded to S3 (supports bundles > 70MB)
- Full Terraform IaC — VPC, subnets, NAT Gateway, RDS, ElastiCache, Lambda, API Gateway, CloudFront

## Architecture

```
User  →  Next.js Frontend (S3)  →  CloudFront  →  API Gateway (REST v1)  →  Lambda  →  Bedrock / RDS PostgreSQL
                                                                               ↕              ↕
                                                                         S3 Documents    ElastiCache Redis
```

| Component        | Technology                                            |
| ---------------- | ----------------------------------------------------- |
| Frontend         | Next.js with Tailwind CSS (static export to S3)       |
| Backend          | FastAPI on AWS Lambda via Mangum                      |
| LLM              | Amazon Bedrock — Nova Lite (chat), Titan (embeddings) |
| Database         | RDS PostgreSQL 16 with pgvector                       |
| Cache            | ElastiCache Redis (session memory)                    |
| Migrations       | Alembic                                               |
| Infrastructure   | Terraform                                             |
| Networking       | VPC, public/private subnets, NAT Gateway, IGW         |
| API              | API Gateway REST v1, CloudFront, API key + quota      |
| Document Storage | S3                                                    |

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── server.py                  # FastAPI application
│   │   └── database/
│   │       ├── alembic.ini            # Alembic configuration
│   │       └── migrations/
│   │           ├── env.py             # Alembic environment (DB URL builder)
│   │           ├── script.py.mako     # Migration template
│   │           └── versions/
│   │               ├── 0001_create_initial_tables.py
│   │               └── 0002_create_session_tables.py
│   ├── lambda_handler.py             # Lambda entry point (Mangum)
│   ├── deploy.py                     # Builds Lambda zip and uploads to S3
│   └── pyproject.toml                # Python dependencies
├── frontend/
│   └── search-knowledge-base-app/    # Next.js application (static export)
├── scripts/
│   ├── deploy.sh                     # Full deployment script
│   └── destroy.sh                    # Tear down infrastructure
└── terraform/
    ├── main.tf                       # Lambda, API Gateway, CloudFront, S3, IAM
    ├── networking.tf                 # VPC, subnets, route tables, NAT GW, security groups
    ├── database.tf                   # RDS PostgreSQL
    ├── elasticache.tf                # ElastiCache Redis
    ├── variables.tf                  # Input variables
    ├── outputs.tf                    # Terraform outputs
    ├── terraform.tfvars              # Variable values
    ├── backend.tf                    # S3 remote state backend
    └── versions.tf                   # Provider configuration
```

## API Endpoints

| Method | Path                    | Description                                                       |
| ------ | ----------------------- | ----------------------------------------------------------------- |
| `GET`  | `/`                     | Root — returns API info                                           |
| `GET`  | `/health`               | Health check                                                      |
| `POST` | `/search`               | Semantic search (max 1000 chars), returns RAG answer with sources |
| `GET`  | `/create_vector`        | Download docs from S3, generate embeddings, store in PostgreSQL   |
| `GET`  | `/session/{session_id}` | Retrieve conversation history from Redis                          |
| `POST` | `/session/end`          | Flush session from Redis to PostgreSQL                            |

All endpoints require an API key via `x-api-key` header. Daily quota: 100 requests.

## Session Memory

### How it works

1. **Session start** — frontend generates a UUID, stored in `sessionStorage` (per tab)
2. **During session** — each Q&A turn is stored in Redis (`session:<id>`), last 5 turns are included in the LLM prompt for conversational context
3. **Session end** — on tab/browser close, `navigator.sendBeacon` calls `/session/end` which flushes the conversation from Redis to PostgreSQL (`user_sessions` + `conversations` tables)
4. **Safety net** — Redis TTL (1 hour) auto-expires sessions if the browser crashes without calling `/session/end`
5. **Page refresh** — conversation is restored from Redis via `GET /session/{session_id}`

### Database tables

- `user_sessions` — maps `user_id` (API key) to `session_id`
- `conversations` — stores Q&A turns permanently, linked to session

## Sample Request and Response

**Question:** what is capital of australia
**Answer:** No relevant documents found in the knowledge base.

**Question:** setup instruction for git on linux
**Answer:** Grounded response with document reference: `udemy/ai-engineering/SETUP-git-linux.md`

### POST /search

**Request:**

```bash
curl -X POST https://<api-gateway-url>/dev/search \
  -H "x-api-key: <your-api-key>" \
  -H "Content-Type: application/json" \
  -d '{"question": "How do I clone a repository in Linux?", "session_id": "550e8400-e29b-41d4-a716-446655440000"}'
```

**Response:**

```json
{
  "answer": "# Clone a Repository in Linux\n\nTo clone a repository...",
  "filenames": ["udemy/ai-engineering/SETUP-git-linux.md"],
  "sources": [
    {
      "filename": "udemy/ai-engineering/SETUP-git-linux.md",
      "similarity": 0.3586,
      "excerpt": "# Setting Up Git on Linux..."
    }
  ]
}
```

### GET /health

```bash
curl https://<api-gateway-url>/dev/health \
  -H "x-api-key: <your-api-key>"
```

```json
{ "status": "healthy" }
```

### When daily quota is reached

```json
{ "message": "Limit Exceeded" }
```

## Prerequisites

- Python 3.12+
- Node.js
- Docker (for Lambda packaging, local PostgreSQL, and local Redis)
- AWS CLI configured with Bedrock model access enabled
- Terraform
- [uv](https://docs.astral.sh/uv/) (Python package manager)

## Local Development

### Backend

```bash
cd backend
uv sync
cp .env.example .env   # fill in DATABASE_URL, AWS credentials
REDIS_ENDPOINT=localhost uv run uvicorn app.server:app --reload --port 8000
```

### Frontend

```bash
cd frontend/search-knowledge-base-app
npm install
npm run dev
```

Open `http://localhost:3000` — it redirects to `/home` where you can search the knowledge base.

### Local Database

Start PostgreSQL with pgvector:

```bash
docker run --name postgres \
    -e POSTGRES_PASSWORD=your_password \
    -p 5432:5432 \
    -d pgvector/pgvector:pg16
```

Migrations run automatically on server startup via Alembic. Set `DATABASE_URL` in your `.env`:

```
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/searchknowledgebase
```

### Local Redis

```bash
docker run --name redis -p 6379:6379 -d redis:7
```

Set `REDIS_ENDPOINT=localhost` in your `.env` or pass it inline when starting the backend.

## Uploading Documents to S3

Documents must be `.md` files organized in subdirectories. Each subdirectory name becomes the `doc_type` metadata.

```
<bucket>/
  guides/
    setup-guide.md
    deployment.md
  tutorials/
    getting-started.md
```

**Steps:**

```bash
# 1. Get bucket name
cd terraform && terraform output documents_bucket_name

# 2. Upload documents
aws s3 sync ./documents/ s3://<bucket-name>/

# Or upload a single file
aws s3 cp my-doc.md s3://<bucket-name>/guides/my-doc.md

# 3. Trigger vectorization
curl https://<api-gateway-url>/dev/create_vector \
  -H "x-api-key: <your-api-key>"
```

## Environment Variables

### Local (`.env`)

| Variable                 | Default                        | Description                            |
| ------------------------ | ------------------------------ | -------------------------------------- |
| `DATABASE_URL`           | —                              | PostgreSQL connection string           |
| `REDIS_ENDPOINT`         | `localhost`                    | Redis host                             |
| `REDIS_PORT`             | `6379`                         | Redis port                             |
| `DEFAULT_AWS_REGION`     | `ap-southeast-2`               | AWS region for Bedrock                 |
| `BEDROCK_MODEL_ID`       | `amazon.nova-lite-v1:0`        | Bedrock LLM model                      |
| `BEDROCK_EMBED_MODEL_ID` | `amazon.titan-embed-text-v2:0` | Bedrock embedding model                |
| `CORS_ORIGINS`           | `http://localhost:3000`        | Allowed CORS origins (comma-separated) |
| `DOCUMENTS_BUCKET`       | —                              | S3 bucket for knowledge base documents |
| `LANGFUSE_PUBLIC_KEY`    | —                              | Langfuse public key (local only)       |
| `LANGFUSE_SECRET_KEY`    | —                              | Langfuse secret key (local only)       |
| `LANGFUSE_HOST`          | `https://cloud.langfuse.com`   | Langfuse host URL                      |

### Lambda (set by Terraform)

| Variable                 | Description                              |
| ------------------------ | ---------------------------------------- |
| `RDS_ENDPOINT`           | RDS instance hostname                    |
| `DB_PORT`                | RDS port                                 |
| `DB_NAME`                | Database name                            |
| `DB_USER`                | Database username                        |
| `DB_PASSWORD_SECRET_ARN` | Secrets Manager ARN for the RDS password |
| `REDIS_ENDPOINT`         | ElastiCache Redis endpoint               |
| `REDIS_PORT`             | ElastiCache Redis port                   |
| `DOCUMENTS_BUCKET`       | S3 bucket for knowledge base documents   |
| `CORS_ORIGINS`           | CloudFront domain                        |
| `BEDROCK_MODEL_ID`       | Bedrock LLM model                        |
| `BEDROCK_EMBED_MODEL_ID` | Bedrock embedding model                  |
| `LANGFUSE_SECRET_ARN`    | Secrets Manager ARN for Langfuse + OpenAI |

## Deployment

```bash
./scripts/deploy.sh dev
```

This script:

1. Builds the Lambda deployment package using Docker
2. Uploads the zip to S3
3. Runs `terraform init` and `terraform apply`
4. Builds the frontend with API URL and key baked in
5. Syncs the static export to the frontend S3 bucket
6. Invalidates the CloudFront cache

### First-time Setup

Create the S3 bucket for Lambda deployments before the first deploy:

```bash
cd terraform
terraform apply -target=aws_s3_bucket.lambda_deployments \
  -var="project_name=search-knowledge-base" \
  -var="environment=dev"
```

### Retrieve API Key

```bash
cd terraform
terraform output api_key
```

## Teardown

```bash
./scripts/destroy.sh dev
```

This deletes the Lambda function first (to release VPC ENIs), then runs `terraform destroy`.

## Terraform Configuration

Key variables in `terraform/terraform.tfvars`:

| Variable                 | Value                          | Description              |
| ------------------------ | ------------------------------ | ------------------------ |
| `project_name`           | `search-knowledge-base`        | Resource name prefix     |
| `environment`            | `dev`                          | Environment name         |
| `bedrock_model_id`       | `amazon.nova-lite-v1:0`        | Bedrock chat model       |
| `bedrock_embed_model_id` | `amazon.titan-embed-text-v2:0` | Bedrock embedding model  |
| `api_daily_quota`        | `100`                          | API requests per day     |
| `lambda_timeout`         | `60`                           | Lambda timeout (seconds) |

## Troubleshooting

### Lambda bundle size exceeds 70MB

AWS Lambda has a 70MB limit for direct zip uploads. This project uses S3-based deployment to avoid this:

1. `deploy.py` builds the zip locally
2. `deploy.sh` uploads it to S3
3. Lambda resource references `s3_bucket` and `s3_key` instead of `filename`

To reduce bundle size further, exclude packages already in the Lambda runtime (e.g. `boto3`, `botocore`) from the deployment zip.

### Lambda code changes not deploying

The Lambda resource uses `source_code_hash` from the S3 object's ETag. If Terraform doesn't detect changes:

```bash
# Re-upload the zip to S3 (deploy.sh does this automatically)
aws s3 cp backend/lambda-deployment.zip s3://<bucket>/lambda-deployment.zip

# Then re-apply
cd terraform && terraform apply
```

### Migrations running on every request

Migrations run at module load time (once per Lambda cold start), not on every request. If you see repeated migration logs, it means Lambda is cold-starting frequently. This is normal for low-traffic environments.

### No documents found after create_vector

Ensure documents are uploaded to S3 in subdirectories:

```bash
# Correct — file is inside a subdirectory
aws s3 cp doc.md s3://<bucket>/guides/doc.md

# Wrong — file is at root level (will be skipped)
aws s3 cp doc.md s3://<bucket>/doc.md
```

Only `.md` files are processed.

### ElastiCache permissions

If you get `AccessDenied` when creating ElastiCache resources, attach the ElastiCache policy to your IAM user:

```bash
aws iam attach-user-policy \
  --user-name <your-iam-username> \
  --policy-arn arn:aws:iam::aws:policy/AmazonElastiCacheFullAccess
```

## Future Enhancements

### Authentication with Clerk

Integrate [Clerk](https://clerk.com/) for user authentication and multi-tenancy:

- Sign up / sign in with email, Google, or GitHub
- Protect API endpoints with JWT verification middleware
- Per-user knowledge bases — scope documents and chunks to the authenticated user
- User dashboard to manage uploaded documents and search history

### Secure API Key with JWT Tokens

The API key is currently embedded in the frontend bundle via `NEXT_PUBLIC_API_KEY`, which exposes it in client-side JavaScript. Replace with JWT-based authentication:

- Issue short-lived JWT tokens after user login (via Clerk or custom auth)
- Validate JWT in a Lambda authorizer attached to API Gateway
- Remove the static API key requirement from frontend
- Rate limiting moves from API key quota to per-user token claims

### Payments with Stripe

Add [Stripe](https://stripe.com/) to turn this into a SaaS product:

- Free tier with limited searches per month and document upload cap
- Pro tier with unlimited searches, larger document storage, and priority embedding processing
- Stripe Checkout for subscription management
- Webhook integration to activate/deactivate features based on subscription status
- Usage-based billing option for high-volume API consumers

## Observability — Langfuse

[Langfuse](https://langfuse.com/) traces all Bedrock LLM calls — token usage, cost, latency, and full prompt/response history.

### What is traced

- **Embedding calls** — `get_embedding()` via `bedrock_client.invoke_model()` (Titan)
- **Chat calls** — `/search` via `bedrock_client.converse()` (Nova Lite), including input/output token counts

### Setup

1. Sign up at [cloud.langfuse.com](https://cloud.langfuse.com) (free tier available)
2. Create a project and get your public/secret keys
3. After `terraform apply`, populate the Secrets Manager secret:

```bash
aws secretsmanager put-secret-value \
  --secret-id "$(cd terraform && terraform output -raw langfuse_secret_arn)" \
  --secret-string '{"langfuse_public_key":"pk-...","langfuse_secret_key":"sk-...","openai_api_key":"sk-..."}'
```

Credentials are stored in AWS Secrets Manager (`langfuse-keys`), not in env vars or code. Lambda reads them on cold start.

### Local development

Add to your `.env`:

```
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

### Dashboard

After making a few searches, open your Langfuse project dashboard to see:
- Traces per request with full prompt and response
- Token usage (input/output) per call
- Cost per model
- Latency breakdown