import json
import os
import tempfile

import boto3
import psycopg2
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel, Field

from alembic import command
from alembic.config import Config

load_dotenv(override=True)

# Run migrations once at module load (Lambda cold start only)
try:
    alembic_ini = os.path.join(os.path.dirname(__file__), "database", "alembic.ini")
    alembic_cfg = Config(alembic_ini)
    command.upgrade(alembic_cfg, "head")
    print("Migrations completed successfully.")
except Exception as e:
    print(f"Migration warning: {e}")

app = FastAPI()

origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

bedrock_client = boto3.client(
    service_name="bedrock-runtime",
    region_name=os.getenv("DEFAULT_AWS_REGION", "ap-southeast-2"),
)

BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")
BEDROCK_EMBED_MODEL_ID = os.getenv("BEDROCK_EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0")


def get_embedding(text: str) -> list[float]:
    response = bedrock_client.invoke_model(
        modelId=BEDROCK_EMBED_MODEL_ID,
        body=json.dumps({"inputText": text}),
        contentType="application/json",
        accept="application/json",
    )
    result = json.loads(response["body"].read())
    return result["embedding"]


def get_database_url():
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    password_secret_arn = os.getenv("DB_PASSWORD_SECRET_ARN")
    if password_secret_arn:
        region = os.getenv("DEFAULT_AWS_REGION", "ap-southeast-2")
        client = boto3.client("secretsmanager", region_name=region)
        secret = json.loads(
            client.get_secret_value(SecretId=password_secret_arn)["SecretString"]
        )
        password = secret["password"]
    else:
        password = os.getenv("DB_PASSWORD", "")

    host = os.getenv("RDS_ENDPOINT", "localhost")
    port = os.getenv("DB_PORT", "5432")
    dbname = os.getenv("DB_NAME", "searchknowledgebase")
    user = os.getenv("DB_USER", "dbadmin")

    return f"postgresql://{user}:{password}@{host}:{port}/{dbname}"


def get_db_connection():
    return psycopg2.connect(get_database_url())


@app.get("/")
async def root():
    return {"message": "Search knowledge base api"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


def download_s3_documents(bucket: str, local_dir: str):
    """Download all documents from S3 bucket to a local temp directory."""
    s3 = boto3.client("s3", region_name=os.getenv("DEFAULT_AWS_REGION", "ap-southeast-2"))
    paginator = s3.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if not key.endswith(".md"):
                continue
            local_path = os.path.join(local_dir, key)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            s3.download_file(bucket, key, local_path)
            print(f"Downloaded s3://{bucket}/{key}")


@app.get("/create_vector")
async def create_vector():
    print("create vector files in the knowledge base")

    bucket = os.getenv("DOCUMENTS_BUCKET")
    if not bucket:
        raise HTTPException(status_code=500, detail="DOCUMENTS_BUCKET not configured")

    with tempfile.TemporaryDirectory() as tmp_dir:
        download_s3_documents(bucket, tmp_dir)

        folders = [
            os.path.join(tmp_dir, d)
            for d in os.listdir(tmp_dir)
            if os.path.isdir(os.path.join(tmp_dir, d))
        ]

        documents = []
        for folder in folders:
            doc_type = os.path.basename(folder)
            loader = DirectoryLoader(
                folder, glob="**/*.md", loader_cls=TextLoader, loader_kwargs={"encoding": "utf-8"}
            )
            folder_docs = loader.load()
            for doc in folder_docs:
                doc.metadata["doc_type"] = doc_type
                doc.metadata["source"] = doc.metadata.get("source", "").replace(tmp_dir + "/", "")
                documents.append(doc)

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = text_splitter.split_documents(documents)

    print(f"Divided into {len(chunks)} chunks")
    print(f"Loaded {len(documents)} documents")

    conn = get_db_connection()
    cur = conn.cursor()

    doc_id_cache = {}
    chunks_stored = 0

    try:
        for i, chunk in enumerate(chunks):
            filename = chunk.metadata.get("source", "unknown")
            doc_type = chunk.metadata.get("doc_type", "unknown")

            if filename not in doc_id_cache:
                cur.execute(
                    "INSERT INTO documents (filename, doc_type) VALUES (%s, %s) RETURNING id",
                    (filename, doc_type),
                )
                doc_id_cache[filename] = cur.fetchone()[0]

            document_id = doc_id_cache[filename]
            embedding = get_embedding(chunk.page_content)
            print(f"Chunk {i}: embedding length = {len(embedding)}")

            cur.execute(
                "INSERT INTO chunks (document_id, chunk_index, content, embedding, metadata) "
                "VALUES (%s, %s, %s, %s, %s)",
                (document_id, i, chunk.page_content, str(embedding), json.dumps(chunk.metadata)),
            )
            chunks_stored += 1

        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error at chunk {i}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed at chunk {i}: {str(e)}")
    finally:
        cur.close()
        conn.close()

    print(f"Stored {chunks_stored} chunks in database")
    return {"status": "completed", "documents": len(doc_id_cache), "chunks_stored": chunks_stored}


class SearchRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)


@app.post("/search")
async def search(request: SearchRequest):
    question_embedding = get_embedding(request.question)

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT c.content, c.metadata, d.filename, 1 - (c.embedding <=> %s::vector) AS similarity "
        "FROM chunks c JOIN documents d ON c.document_id = d.id "
        "WHERE 1 - (c.embedding <=> %s::vector) > 0.2 "
        "ORDER BY c.embedding <=> %s::vector LIMIT 5",
        (str(question_embedding), str(question_embedding), str(question_embedding)),
    )
    results = cur.fetchall()
    cur.close()
    conn.close()

    if not results:
        return {
            "answer": "No relevant documents found in the knowledge base.The search is grounded uploaded documents with only one document related to setup git on linux",
            "filenames": [],
            "sources": [],
        }

    context = "\n\n".join([f"[Source: {row[2]}]\n{row[0]}" for row in results])

    prompt = (
        f"Based on the following knowledge base excerpts, answer the question. return in .md format\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {request.question}\n\n"
        f"Answer:"
    )

    response = bedrock_client.converse(
        modelId=BEDROCK_MODEL_ID,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 2000, "temperature": 0.7, "topP": 0.9},
    )
    answer = response["output"]["message"]["content"][0]["text"]

    best_by_file: dict[str, tuple] = {}
    for row in results:
        filename = row[2]
        similarity = row[3]
        if filename not in best_by_file or similarity > best_by_file[filename][3]:
            best_by_file[filename] = row

    filenames = list(best_by_file.keys())
    sources = [
        {"filename": row[2], "similarity": round(row[3], 4), "excerpt": row[0][:200]}
        for row in best_by_file.values()
    ]

    return {
        "answer": answer,
        "filenames": filenames,
        "sources": sources,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
