# Search Knowledge Base

Semantic search API over local documents using AWS Bedrock embeddings and PostgreSQL with pgvector.

The problem targeted is to locate a training video based on semantic search. We watch training videos but later forget which one has the details. For example, if I want to search which training video covers how to setup Mac for Python 3, I can search among a vector database of transcripts and `.md` files attached to the video.

The more important use case is when the vector database is created from a video file — a lecture delivered by a teacher in school, a court case discussed by a lawyer, or a politician's statement from 50 years ago. We can convert video into transcript and create vectors from it.

## Features

- Semantic search over markdown documents using vector embeddings
- RAG (Retrieval-Augmented Generation) powered answers via Amazon Bedrock
- Document chunking with LangChain text splitters
- Vector similarity search using PostgreSQL with pgvector
- REST API with daily request quota (100/day) and API key authentication
- CloudFront CDN in front of API Gateway
- Automated deployment via shell scripts and Terraform
- Lambda deployment packages uploaded to S3 (supports bundles > 70MB)
- Input validation (max 1000 characters per search query)
- Cost control: daily quota per API key limits LLM calls, input size limit controls token usage

## Architecture

```
Frontend (Next.js)  -->  CloudFront  -->  API Gateway (REST)  -->  Lambda  -->  Bedrock / PostgreSQL
```

- **Frontend** - Next.js app with Tailwind CSS
- **Backend** - FastAPI running on AWS Lambda via Mangum
- **LLM** - Amazon Bedrock (Nova Lite for chat, Titan for embeddings)
- **Database** - PostgreSQL with pgvector for vector similarity search
- **Infrastructure** - Terraform (VPC, subnets, API Gateway, Lambda, CloudFront, S3)

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   └── server.py          # FastAPI application
│   ├── lambda_handler.py      # Lambda entry point (Mangum)
│   ├── deploy.py              # Builds Lambda zip and uploads to S3
│   └── pyproject.toml         # Python dependencies
├── frontend/
│   └── search-knowledge-base-app/   # Next.js application
├── scripts/
│   ├── deploy.sh              # Full deployment script
│   └── destroy.sh             # Tear down infrastructure
└── terraform/
    ├── main.tf                # Lambda, API Gateway, CloudFront, S3, IAM
    ├── networking.tf          # VPC, subnets, route tables, security groups
    ├── variables.tf           # Input variables
    ├── outputs.tf             # Terraform outputs
    ├── terraform.tfvars       # Variable values
    ├── backend.tf             # S3 remote state backend
    └── versions.tf            # Provider configuration
```

## API Endpoints

| Method | Path              | Description                                              |
|--------|-------------------|----------------------------------------------------------|
| `GET`  | `/`               | Root — returns API info                                  |
| `GET`  | `/health`         | Health check                                             |
| `POST` | `/search`         | Semantic search — takes a question (max 1000 chars), returns LLM answer with sources |
| `GET`  | `/create_vector`  | Load documents, generate embeddings, store in PostgreSQL |

All endpoints require an API key via `x-api-key` header. Daily quota: 100 requests.

## Sample Request and Response

### POST /search

**Request:**

```bash
curl -X POST https://<api-gateway-url>/dev/search \
  -H "x-api-key: <your-api-key>" \
  -H "Content-Type: application/json" \
  -d '{"question": "How do I clone a repository in Linux?"}'
```

**Response:**

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

### GET /health

```bash
curl https://<api-gateway-url>/dev/health \
  -H "x-api-key: <your-api-key>"
```

```json
{
  "status": "healthy"
}
```

### When daily quota is reached

```json
{
  "message": "Limit Exceeded"
}
```

## Prerequisites

- Python 3.12+
- Node.js
- Docker (for Lambda packaging and PostgreSQL)
- AWS CLI configured with Bedrock model access enabled
- Terraform
- [uv](https://docs.astral.sh/uv/) (Python package manager)

## Local Development

### Backend

```bash
cd backend
uv sync
cp .env.example .env   # fill in values
uv run uvicorn app.server:app --reload --port 8000
```

### Frontend

```bash
cd frontend/search-knowledge-base-app
npm install
npm run dev
```

Open `http://localhost:3000` — it redirects to `/home` where you can search the knowledge base.

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
|--------------------------|--------------------------------|----------------------------------------|
| `DATABASE_URL`           | —                              | PostgreSQL connection string           |
| `DEFAULT_AWS_REGION`     | `ap-southeast-2`               | AWS region for Bedrock                 |
| `BEDROCK_MODEL_ID`       | `amazon.nova-lite-v1:0`        | Bedrock LLM model                      |
| `BEDROCK_EMBED_MODEL_ID` | `amazon.titan-embed-text-v2:0` | Bedrock embedding model                |
| `CORS_ORIGINS`           | `http://localhost:3000`        | Allowed CORS origins (comma-separated) |

## Deployment

```bash
./scripts/deploy.sh dev
```

This script:
1. Builds the Lambda deployment package using Docker
2. Uploads the zip to S3
3. Runs `terraform init` and `terraform apply`

### First-time S3 bucket setup

If the Lambda S3 bucket doesn't exist yet, create it first:

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

## Configuration

Key variables in `terraform/terraform.tfvars`:

| Variable                 | Default                          | Description              |
|--------------------------|----------------------------------|--------------------------|
| `project_name`           | `search-knowledge-base`          | Resource name prefix     |
| `environment`            | `dev`                            | Environment name         |
| `bedrock_model_id`       | `amazon.nova-lite-v1:0`          | Bedrock chat model       |
| `bedrock_embed_model_id` | `amazon.titan-embed-text-v2:0`   | Bedrock embedding model  |
| `api_daily_quota`        | `100`                            | API requests per day     |
| `lambda_timeout`         | `60`                             | Lambda timeout (seconds) |

## Troubleshooting

### Lambda bundle size exceeds 70MB

AWS Lambda has a 70MB limit for direct zip uploads via the `CreateFunction` API. If your deployment zip exceeds this:

1. Upload the zip to S3 instead of using direct file upload
2. Reference the S3 bucket and key in the Lambda Terraform resource:
   ```hcl
   resource "aws_lambda_function" "api" {
     s3_bucket = aws_s3_bucket.lambda_deployments.id
     s3_key    = "lambda-deployment.zip"
     ...
   }
   ```
3. To reduce bundle size, exclude packages already in the Lambda runtime (e.g. `boto3`, `botocore`) from the deployment zip
4. Remove unused dependencies from `pyproject.toml`

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
