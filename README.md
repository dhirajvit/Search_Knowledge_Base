# Search Knowledge Base

Semantic search over documents using AWS Bedrock embeddings, PostgreSQL with pgvector, and RAG-powered answers.

The problem targeted is to locate a training video based on semantic search. We watch training videos but later forget which one has the details. For example, if I want to search which training video covers how to setup Mac for Python 3, I can search among a vector database of transcripts and `.md` files attached to the video.

The more important use case is when the vector database is created from a video file — a lecture delivered by a teacher in school, a court case discussed by a lawyer, or a politician's statement from 50 years ago. We can convert video into transcript and create vectors from it.

## Features

- Semantic search over markdown documents using vector embeddings
- RAG (Retrieval-Augmented Generation) powered answers via Amazon Bedrock
- Document chunking with LangChain text splitters
- Vector similarity search using PostgreSQL with pgvector
- Documents stored in S3 — downloaded and vectorized on demand
- Database migrations managed by Alembic (auto-run on Lambda cold start)
- REST API with daily request quota and API key authentication
- CloudFront CDN in front of API Gateway
- Input validation (max 1000 characters) on both backend and frontend
- Lambda deployment packages uploaded to S3 (supports bundles > 70MB)
- Full Terraform IaC — VPC, subnets, NAT Gateway, RDS, Lambda, API Gateway, CloudFront

## Architecture

```
User  →  Next.js Frontend  →  CloudFront  →  API Gateway (REST v1)  →  Lambda  →  Bedrock / RDS PostgreSQL
                                                                           ↕
                                                                     S3 Documents
```

| Component          | Technology                                          |
|--------------------|-----------------------------------------------------|
| Frontend           | Next.js with Tailwind CSS                           |
| Backend            | FastAPI on AWS Lambda via Mangum                    |
| LLM                | Amazon Bedrock — Nova Lite (chat), Titan (embeddings) |
| Database           | RDS PostgreSQL 16 with pgvector                     |
| Migrations         | Alembic                                             |
| Infrastructure     | Terraform                                           |
| Networking         | VPC, public/private subnets, NAT Gateway, IGW       |
| API                | API Gateway REST v1, CloudFront, API key + quota    |
| Document Storage   | S3                                                  |

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
│   │               └── 0001_create_initial_tables.py
│   ├── lambda_handler.py             # Lambda entry point (Mangum)
│   ├── deploy.py                     # Builds Lambda zip and uploads to S3
│   └── pyproject.toml                # Python dependencies
├── frontend/
│   └── search-knowledge-base-app/    # Next.js application
├── scripts/
│   ├── deploy.sh                     # Full deployment script
│   └── destroy.sh                    # Tear down infrastructure
└── terraform/
    ├── main.tf                       # Lambda, API Gateway, CloudFront, S3, IAM
    ├── networking.tf                 # VPC, subnets, route tables, NAT GW, security groups
    ├── database.tf                   # RDS PostgreSQL
    ├── variables.tf                  # Input variables
    ├── outputs.tf                    # Terraform outputs
    ├── terraform.tfvars              # Variable values
    ├── backend.tf                    # S3 remote state backend
    └── versions.tf                   # Provider configuration
```

## API Endpoints

| Method | Path             | Description                                      |
|--------|------------------|--------------------------------------------------|
| `GET`  | `/`              | Root — returns API info                          |
| `GET`  | `/health`        | Health check                                     |
| `POST` | `/search`        | Semantic search (max 1000 chars), returns RAG answer with sources |
| `GET`  | `/create_vector` | Download docs from S3, generate embeddings, store in PostgreSQL |

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
{"status": "healthy"}
```

### When daily quota is reached

```json
{"message": "Limit Exceeded"}
```

## Prerequisites

- Python 3.12+
- Node.js
- Docker (for Lambda packaging and local PostgreSQL)
- AWS CLI configured with Bedrock model access enabled
- Terraform
- [uv](https://docs.astral.sh/uv/) (Python package manager)

## Local Development

### Backend

```bash
cd backend
uv sync
cp .env.example .env   # fill in DATABASE_URL, AWS credentials
uv run uvicorn app.server:app --reload --port 8000
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
|--------------------------|--------------------------------|----------------------------------------|
| `DATABASE_URL`           | —                              | PostgreSQL connection string           |
| `DEFAULT_AWS_REGION`     | `ap-southeast-2`               | AWS region for Bedrock                 |
| `BEDROCK_MODEL_ID`       | `amazon.nova-lite-v1:0`        | Bedrock LLM model                      |
| `BEDROCK_EMBED_MODEL_ID` | `amazon.titan-embed-text-v2:0` | Bedrock embedding model                |
| `CORS_ORIGINS`           | `http://localhost:3000`        | Allowed CORS origins (comma-separated) |
| `DOCUMENTS_BUCKET`       | —                              | S3 bucket for knowledge base documents |

### Lambda (set by Terraform)

| Variable                 | Description                                |
|--------------------------|--------------------------------------------|
| `RDS_ENDPOINT`           | RDS instance hostname                      |
| `DB_PORT`                | RDS port                                   |
| `DB_NAME`                | Database name                              |
| `DB_USER`                | Database username                          |
| `DB_PASSWORD_SECRET_ARN` | Secrets Manager ARN for the RDS password   |
| `DOCUMENTS_BUCKET`       | S3 bucket for knowledge base documents     |
| `CORS_ORIGINS`           | CloudFront domain                          |
| `BEDROCK_MODEL_ID`       | Bedrock LLM model                          |
| `BEDROCK_EMBED_MODEL_ID` | Bedrock embedding model                    |

## Deployment

```bash
./scripts/deploy.sh dev
```

This script:
1. Builds the Lambda deployment package using Docker
2. Uploads the zip to S3
3. Runs `terraform init` and `terraform apply`

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

| Variable                 | Value                            | Description              |
|--------------------------|----------------------------------|--------------------------|
| `project_name`           | `search-knowledge-base`          | Resource name prefix     |
| `environment`            | `dev`                            | Environment name         |
| `bedrock_model_id`       | `amazon.nova-lite-v1:0`          | Bedrock chat model       |
| `bedrock_embed_model_id` | `amazon.titan-embed-text-v2:0`   | Bedrock embedding model  |
| `api_daily_quota`        | `100`                            | API requests per day     |
| `lambda_timeout`         | `60`                             | Lambda timeout (seconds) |

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
