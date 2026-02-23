import json
import os

import boto3

def init_langfuse():
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")

    if not public_key:
        langfuse_secret_arn = os.getenv("LANGFUSE_SECRET_ARN")
        if langfuse_secret_arn:
            region = os.getenv("DEFAULT_AWS_REGION", "ap-southeast-2")
            client = boto3.client("secretsmanager", region_name=region)
            secret = json.loads(
                client.get_secret_value(SecretId=langfuse_secret_arn)["SecretString"]
            )
            os.environ["LANGFUSE_PUBLIC_KEY"] = secret.get("langfuse_public_key", "")
            os.environ["LANGFUSE_SECRET_KEY"] = secret.get("langfuse_secret_key", "")
            if secret.get("openai_api_key"):
                os.environ["OPENAI_API_KEY"] = secret["openai_api_key"]
            print("Langfuse configured from Secrets Manager")
            return True

    if public_key:
        print("Langfuse configured from env vars")
        return True

    print("Langfuse not configured — tracing disabled")
    return False
