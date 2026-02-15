import os
import shutil
import zipfile
import subprocess
import boto3


def main():
    print("search knowledge base creating Lambda deployment package...")

    # Clean up
    if os.path.exists("lambda-package"):
        shutil.rmtree("lambda-package")
    if os.path.exists("lambda-deployment.zip"):
        os.remove("lambda-deployment.zip")

    # Create package directory
    os.makedirs("lambda-package")

    # -------------------------
    # 1️⃣ Compile dependencies from uv.lock
    # -------------------------
    print("Compiling Lambda requirements from uv.lock...")
    subprocess.run(
        [
            "uv",
            "pip",
            "compile",
            "pyproject.toml",
            "-o",
            "lambda-requirements.txt",
        ],
        check=True,
    )

    # Install dependencies using Docker with Lambda runtime image
    print("Installing dependencies for Lambda runtime...")

    # Use the official AWS Lambda Python 3.12 image
    # This ensures compatibility with Lambda's runtime environment
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{os.getcwd()}:/var/task",
            "--platform",
            "linux/amd64",  # Force x86_64 architecture
            "--entrypoint",
            "",  # Override the default entrypoint
            "public.ecr.aws/lambda/python:3.12",
            "/bin/sh",
            "-c",
            "pip install --target /var/task/lambda-package -r /var/task/lambda-requirements.txt --upgrade",
      ],
        check=True,
    )

    # Copy application files
    print("lambda_handler...")
    for file in ["lambda_handler.py",]:
        if os.path.exists(file):
            print(f"{file} exists")
            shutil.copy2(file, "lambda-package/")
    
    SRC_DIR = "app"
    DEST_DIR = "lambda-package/app"

    print("Copying application directory...")

    if not os.path.exists(SRC_DIR):
        raise FileNotFoundError(f"Source directory not found: {SRC_DIR}")

    shutil.copytree(
        SRC_DIR,
        DEST_DIR,
        dirs_exist_ok=True
    )

    # Create zip
    print("Creating zip file...")
    with zipfile.ZipFile("lambda-deployment.zip", "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk("lambda-package"):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, "lambda-package")
                zipf.write(file_path, arcname)

    # Show package size
    size_mb = os.path.getsize("lambda-deployment.zip") / (1024 * 1024)
    print(f"✓ Created lambda-deployment.zip ({size_mb:.2f} MB)")

    # Upload to S3
    project_name = os.environ.get("PROJECT_NAME", "search-knowledge-base")
    environment = os.environ.get("ENVIRONMENT", "dev")
    region = os.environ.get("AWS_REGION", "ap-southeast-2")

    sts = boto3.client("sts", region_name=region)
    account_id = sts.get_caller_identity()["Account"]
    bucket_name = f"{project_name}-{environment}-lambda-deployments-{account_id}"

    print(f"Uploading to s3://{bucket_name}/lambda-deployment.zip ...")
    s3 = boto3.client("s3", region_name=region)
    s3.upload_file("lambda-deployment.zip", bucket_name, "lambda-deployment.zip")
    print(f"✓ Uploaded to S3")


if __name__ == "__main__":
    main()