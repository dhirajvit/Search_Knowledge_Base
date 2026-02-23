import json
import os
import tempfile
from typing import Optional

import boto3
import redis
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langfuse import get_client, observe
from .langfuse.langfuse import init_langfuse
from .database.database_init import get_db_connection, run_migrations
from .bedrock.llm import call_bedrock
from .PIIRedaction import PIIRedactor
from .embedding import get_embedding, search_semantic_cache, store_semantic_cache
from pydantic import BaseModel, Field

load_dotenv(override=True)

# Run migrations once at module load (Lambda cold start only)
run_migrations()

app = FastAPI()

origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")

REDIS_HOST = os.getenv("REDIS_ENDPOINT", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
SESSION_TTL = 3600  # 1 hour

redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

langfuse_enabled = init_langfuse()
redactor = PIIRedactor()




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
    session_id: Optional[str] = None


@app.post("/search")
@observe(capture_input=False, capture_output=False)
async def search(request: SearchRequest):
    question_embedding = get_embedding(request.question)

    cached_answer, similarity = search_semantic_cache(question_embedding)
    print(f"cached_result: {cached_answer}, similarity: {similarity}")
    if cached_answer:
        response = {"answer": cached_answer, "filenames": [], "sources": []}
        get_client().update_current_span(
            input=redactor.redact(request.question),
            output=redactor.redact_dict(response),
            metadata={"cache_hit": True, "similarity": similarity},
        )
        return response

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT c.content, c.metadata, d.filename, 1 - (c.embedding <=> %s::vector) AS similarity "
        "FROM chunks c JOIN documents d ON c.document_id = d.id "
        "WHERE 1 - (c.embedding <=> %s::vector) > 0.1 "
        "ORDER BY c.embedding <=> %s::vector LIMIT 5",
        (str(question_embedding), str(question_embedding), str(question_embedding)),
    )
    results = cur.fetchall()
    cur.close()
    conn.close()

    if not results:
        answer = "No relevant documents found in the knowledge base.The solution is grounded to search only uploaded document. As of now only one uploaded document setup git on linux"
        sources = []
        filenames = []
    else:
        context = "\n\n".join([f"[Source: {row[2]}]\n{row[0]}" for row in results])

        # Build conversation history from Redis
        conversation_history = ""
        if request.session_id:
            redis_key = f"session:{request.session_id}"
            previous_turns = redis_client.lrange(redis_key, 0, -1)
            if previous_turns:
                turns = [json.loads(t) for t in previous_turns]
                conversation_history = "Previous conversation:\n"
                for turn in turns[-5:]:  # last 5 turns for context
                    conversation_history += f"Q: {turn['question']}\nA: {turn['answer']}\n\n"

        prompt = (
            f"Based on the following knowledge base excerpts, answer the question. return in .md format\n\n"
            f"{conversation_history}"
            f"Context:\n{context}\n\n"
            f"Question: {request.question}\n\n"
            f"Answer:"
        )

        llm_response = call_bedrock(prompt, model=BEDROCK_MODEL_ID)
        answer = llm_response.content

        store_semantic_cache(question_embedding, answer)

        best_by_file: dict[str, tuple] = {}
        for row in results:
            filename = row[2]
            row_similarity = row[3]
            if filename not in best_by_file or row_similarity > best_by_file[filename][3]:
                best_by_file[filename] = row

        filenames = list(best_by_file.keys())
        sources = [
            {"filename": row[2], "similarity": round(row[3], 4), "excerpt": row[0][:200]}
            for row in best_by_file.values()
        ]

    # Store turn in Redis
    if request.session_id:
        redis_key = f"session:{request.session_id}"
        turn = json.dumps({
            "question": request.question,
            "answer": answer,
            "sources": sources,
        })
        redis_client.rpush(redis_key, turn)
        redis_client.expire(redis_key, SESSION_TTL)

    response = {
        "answer": answer,
        "filenames": filenames,
        "sources": sources,
    }

    get_client().update_current_span(
        input=redactor.redact(request.question),
        output=redactor.redact_dict(response),
        metadata={"cache_hit": False, "similarity": None},
    )

    return response


class SessionEndRequest(BaseModel):
    session_id: str
    user_id: str


@app.post("/session/end")
async def end_session(request: SessionEndRequest):
    redis_key = f"session:{request.session_id}"
    turns = redis_client.lrange(redis_key, 0, -1)

    if not turns:
        return {"status": "no_conversation"}

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Create user-session mapping
        cur.execute(
            "INSERT INTO user_sessions (user_id, session_id) VALUES (%s, %s) "
            "ON CONFLICT (session_id) DO NOTHING",
            (request.user_id, request.session_id),
        )

        # Insert all conversation turns
        for turn_json in turns:
            turn = json.loads(turn_json)
            cur.execute(
                "INSERT INTO conversations (session_id, question, answer, sources) "
                "VALUES (%s, %s, %s, %s)",
                (request.session_id, turn["question"], turn["answer"], json.dumps(turn["sources"])),
            )

        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save session: {str(e)}")
    finally:
        cur.close()
        conn.close()

    # Clean up Redis
    redis_client.delete(redis_key)

    return {"status": "saved", "turns": len(turns)}


@app.get("/session/{session_id}")
async def get_session(session_id: str):
    redis_key = f"session:{session_id}"
    turns = redis_client.lrange(redis_key, 0, -1)

    return {
        "session_id": session_id,
        "turns": [json.loads(t) for t in turns],
    }


@app.on_event("shutdown")
async def shutdown():
    if langfuse_enabled:
        get_client().flush()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
