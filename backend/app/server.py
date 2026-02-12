from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import boto3
from botocore.exceptions import ClientError
import glob
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
import os
import json
import psycopg2
from psycopg2.extras import execute_values

# Load environment variables
load_dotenv(override=True)
MODEL = "gpt-4.1-nano"

app = FastAPI()
# Configure CORS
origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Bedrock client
bedrock_client = boto3.client(
    service_name="bedrock-runtime", 
    region_name=os.getenv("DEFAULT_AWS_REGION", "ap-southeast-2")
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


def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))


@app.get("/")
async def root():
    return {"message": "Search knowledge base api"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/create_vector")
async def create_vector():
  print(f"create vector files in the knowledge base")
  # TODO read folders from S3 
  folders = glob.glob("documents/*")
  documents = []
  for folder in folders:
    doc_type = os.path.basename(folder)
    loader = DirectoryLoader(folder, glob="**/*.md", loader_cls=TextLoader, loader_kwargs={'encoding': 'utf-8'})
    folder_docs = loader.load()
    for doc in folder_docs:
      doc.metadata["doc_type"] = doc_type
      documents.append(doc)


  text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
  chunks = text_splitter.split_documents(documents)

  print(f"Divided into {len(chunks)} chunks")
  print(f"Loaded {len(documents)} documents")

  conn = get_db_connection()
  cur = conn.cursor()

  # Track inserted document IDs by filename
  doc_id_cache = {}
  chunks_stored = 0

  for i, chunk in enumerate(chunks):
    filename = chunk.metadata.get("source", "unknown")
    doc_type = chunk.metadata.get("doc_type", "unknown")

    # Insert document row if not already inserted
    if filename not in doc_id_cache:
      cur.execute(
        "INSERT INTO documents (filename, doc_type) VALUES (%s, %s) RETURNING id",
        (filename, doc_type)
      )
      doc_id_cache[filename] = cur.fetchone()[0]

    document_id = doc_id_cache[filename]
    embedding = get_embedding(chunk.page_content)

    cur.execute(
      "INSERT INTO chunks (document_id, chunk_index, content, embedding, metadata) VALUES (%s, %s, %s, %s, %s)",
      (document_id, i, chunk.page_content, str(embedding), json.dumps(chunk.metadata))
    )
    chunks_stored += 1

  conn.commit()
  cur.close()
  conn.close()

  print(f"Stored {chunks_stored} chunks in database")

  return {"status": "completed", "documents": len(doc_id_cache), "chunks_stored": chunks_stored}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)