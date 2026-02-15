#!/bin/bash
set -e

ENVIRONMENT=${1:-dev}          # dev 
PROJECT_NAME=${2:-search-knowledge-base}

echo "🚀 Deploying ${PROJECT_NAME} to ${ENVIRONMENT}..."

# Build Lambda package
cd "$(dirname "$0")/.."        # project root
echo "📦 Building Lambda package..."
(cd backend && uv run deploy.py)

#  Upload Lambda zip to S3
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=${DEFAULT_AWS_REGION:-ap-southeast-2}
S3_BUCKET="${PROJECT_NAME}-${ENVIRONMENT}-lambda-deployments-${AWS_ACCOUNT_ID}"
echo "📤 Uploading Lambda zip to s3://${S3_BUCKET}/lambda-deployment.zip ..."
aws s3 cp backend/lambda-deployment.zip "s3://${S3_BUCKET}/lambda-deployment.zip" --region "${AWS_REGION}"

#  Terraform workspace & apply
cd terraform

# TODO dynamo db lock is disabled to delay creation the table
terraform init -lock=false -input=false \
  -backend-config="bucket=search-knowledge-base-terraform-state-${AWS_ACCOUNT_ID}" \
  -backend-config="key=${ENVIRONMENT}/terraform.tfstate" \
  -backend-config="region=${AWS_REGION}" \
  # -backend-config="dynamodb_table=search-knowledge-base-terraform-locks" \
  # -backend-config="encrypt=true"

if ! terraform workspace list | grep -q "$ENVIRONMENT"; then
  terraform workspace new "$ENVIRONMENT"
else
  terraform workspace select "$ENVIRONMENT"
fi



  TF_APPLY_CMD=(terraform apply -var="project_name=$PROJECT_NAME" -var="environment=$ENVIRONMENT" -auto-approve)

echo "🎯 Applying Terraform..."
"${TF_APPLY_CMD[@]}"

API_URL=$(terraform output -raw api_gateway_url)

echo -e "\n✅ Deployment complete!"
echo "🌐 CloudFront URL : $(terraform -chdir=terraform output -raw cloudfront_url)"
echo "📡 API Gateway    : $API_URL"