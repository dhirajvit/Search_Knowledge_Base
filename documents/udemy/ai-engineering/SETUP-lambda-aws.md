# Setting Up an AWS Lambda Function

## Prerequisites

- AWS account
- AWS CLI installed and configured (`aws configure`)
- Python 3.12+ installed locally
- An IAM role with Lambda execution permissions

## Step 1: Install AWS CLI

```bash
# macOS
brew install awscli

# Linux
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
```

Verify:

```bash
aws --version
```

## Step 2: Configure AWS Credentials

```bash
aws configure
```

Enter your Access Key ID, Secret Access Key, default region, and output format.

## Step 3: Create an IAM Role for Lambda

```bash
aws iam create-role \
  --role-name lambda-execution-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "lambda.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'
```

Attach the basic execution policy:

```bash
aws iam attach-role-policy \
  --role-name lambda-execution-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
```

Note the Role ARN from the output — you'll need it in Step 5.

## Step 4: Write the Lambda Function

Create `lambda_function.py`:

```python
import json

def handler(event, context):
    body = json.loads(event.get("body", "{}"))
    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Hello from Lambda", "input": body})
    }
```

## Step 5: Package and Deploy

Zip the function:

```bash
zip function.zip lambda_function.py
```

Create the Lambda function:

```bash
aws lambda create-function \
  --function-name my-function \
  --runtime python3.12 \
  --role arn:aws:iam::ACCOUNT_ID:role/lambda-execution-role \
  --handler lambda_function.handler \
  --zip-file fileb://function.zip
```

Replace `ACCOUNT_ID` with your AWS account ID.

## Step 6: Test the Function

```bash
aws lambda invoke \
  --function-name my-function \
  --payload '{"body": "{\"name\": \"test\"}"}' \
  output.json

cat output.json
```

## Step 7: Update the Function (after code changes)

```bash
zip function.zip lambda_function.py

aws lambda update-function-code \
  --function-name my-function \
  --zip-file fileb://function.zip
```

## Step 8: Add an API Gateway Trigger (optional)

To expose the Lambda as an HTTP endpoint:

```bash
aws apigatewayv2 create-api \
  --name my-api \
  --protocol-type HTTP \
  --target arn:aws:lambda:REGION:ACCOUNT_ID:function:my-function
```

This gives you a public URL to invoke the function via HTTP.

## Step 9: Adding Dependencies

If your function needs external packages:

```bash
mkdir package
pip install -t package/ requests boto3
cd package && zip -r ../function.zip .
cd .. && zip function.zip lambda_function.py
```

Then deploy with `aws lambda update-function-code` as in Step 7.

## Useful Commands

| Command | Description |
|---|---|
| `aws lambda list-functions` | List all Lambda functions |
| `aws lambda get-function --function-name my-function` | Get function details |
| `aws lambda delete-function --function-name my-function` | Delete a function |
| `aws logs tail /aws/lambda/my-function --follow` | Tail CloudWatch logs |

## Environment Variables

Set env vars for your Lambda:

```bash
aws lambda update-function-configuration \
  --function-name my-function \
  --environment "Variables={DB_HOST=localhost,API_KEY=your-key}"
```

Access them in code with `os.environ["DB_HOST"]`.
