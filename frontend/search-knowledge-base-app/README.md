# Search Knowledge Base

A semantic search application that lets users query a knowledge base of documents using natural language. Documents are chunked, embedded, and stored in PostgreSQL with pgvector. User queries are matched against stored embeddings and answered using AWS Bedrock LLM.

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

| Method | Path              | Description                                |
|--------|-------------------|--------------------------------------------|
| GET    | `/`               | Root - returns API info                    |
| GET    | `/health`         | Health check                               |
| POST   | `/search`         | Search the knowledge base (max 1000 chars) |
| GET    | `/create_vector`  | Ingest documents and create embeddings     |

All endpoints require an API key via `x-api-key` header. Daily quota: 100 requests.

## Prerequisites

- Python 3.12+
- Node.js
- Docker (for Lambda packaging)
- AWS CLI configured
- Terraform
- uv (Python package manager)

## Local Development

### Backend

```bash
cd backend
uv sync
uv run uvicorn app.server:app --reload --port 8000
```

### Frontend

```bash
cd frontend/search-knowledge-base-app
npm install
npm run dev
```

## Deployment

```bash
./scripts/deploy.sh dev
```

This script:
1. Builds the Lambda deployment package using Docker
2. Uploads the zip to S3
3. Runs `terraform init` and `terraform apply`

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
  "answer": "To clone a repository in Linux, use the `git clone` command followed by the repository URL...",
  "filenames": ["documents/git/cloning.md"],
  "sources": [
    {
      "filename": "documents/git/cloning.md",
      "similarity": 0.8921,
      "excerpt": "Git clone creates a local copy of a repository..."
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
