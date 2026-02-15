#!/bin/bash
set -e

# Check if environment parameter is provided
if [ $# -eq 0 ]; then
    echo "❌ Error: Environment parameter is required"
    echo "Usage: $0 <environment>"
    echo "Example: $0 dev"
    echo "Available environments: dev"
    exit 1
fi

ENVIRONMENT=$1
PROJECT_NAME=${2:-search-knowledge-base}

echo "🗑️ Preparing to destroy ${PROJECT_NAME}-${ENVIRONMENT} infrastructure..."

# Get AWS Account ID and Region
if [ -z "$AWS_ACCOUNT_ID" ]; then
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
fi
AWS_REGION=${DEFAULT_AWS_REGION:-${AWS_REGION:-ap-southeast-2}}

# Navigate to terraform directory
cd "$(dirname "$0")/../terraform"

# Initialize terraform with S3 backend
echo "🔧 Initializing Terraform with S3 backend..."
# TODO dynamo db lock is disabled to delay creation the table
terraform init -input=false \
  -backend-config="bucket=search-knowledge-base-terraform-state-${AWS_ACCOUNT_ID}" \
  -backend-config="key=${ENVIRONMENT}/terraform.tfstate" \
  -backend-config="region=${AWS_REGION}" \
#   -backend-config="dynamodb_table=search-knowledge-base-terraform-locks" \
#   -backend-config="encrypt=true"

# Check if workspace exists
if ! terraform workspace list | grep -q "$ENVIRONMENT"; then
    echo "❌ Error: Workspace '$ENVIRONMENT' does not exist"
    echo "Available workspaces:"
    terraform workspace list
    exit 1
fi

# Select the workspace
terraform workspace select "$ENVIRONMENT"

echo "🔥 Running terraform destroy..."

# Create a dummy lambda zip if it doesn't exist (needed for destroy in GitHub Actions)
if [ ! -f "../backend/lambda-deployment.zip" ]; then
    echo "Creating dummy lambda package for destroy operation..."
    echo "dummy" | zip ../backend/lambda-deployment.zip -
fi

# Delete Lambda function first to allow ENIs to be cleaned up
echo "⏳ Removing Lambda function to cleanup VPC ENIs..."

LAMBDA_NAME="${PROJECT_NAME}-${ENVIRONMENT}-api"

if aws lambda get-function --function-name "$LAMBDA_NAME" 2>/dev/null; then
    aws lambda delete-function --function-name "$LAMBDA_NAME"
    echo "  Waiting 30 seconds for ENIs to be released..."
    sleep 30
else
    echo "  Lambda function not found or already deleted"
fi

terraform destroy -var="project_name=$PROJECT_NAME" -var="environment=$ENVIRONMENT" -auto-approve

echo "✅ Infrastructure for ${ENVIRONMENT} has been destroyed!"
echo ""
echo "💡 To remove the workspace completely, run:"
echo "   terraform workspace select default"
echo "   terraform workspace delete $ENVIRONMENT"