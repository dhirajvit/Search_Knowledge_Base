import json
import os
from typing import Optional

from langfuse import get_client, observe
from .bedrock.llm import bedrock_client
from .database.database_init import get_db_connection

BEDROCK_EMBED_MODEL_ID = os.getenv("BEDROCK_EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0")


@observe(as_type="embedding")
def get_embedding(text: str) -> list[float]:
    response = bedrock_client.invoke_model(
        modelId=BEDROCK_EMBED_MODEL_ID,
        body=json.dumps({"inputText": text}),
        contentType="application/json",
        accept="application/json",
    )
    result = json.loads(response["body"].read())

    get_client().update_current_generation(
        model=BEDROCK_EMBED_MODEL_ID,
        usage_details={"input": len(text.split())},
    )

    return result["embedding"]


def search_semantic_cache(embedding: list[float], threshold: float = 0.95) -> tuple[Optional[str], Optional[float]]:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT answer, 1 - (question_embedding <=> %s::vector) AS similarity "
        "FROM semantic_cache "
        "WHERE 1 - (question_embedding <=> %s::vector) >= %s "
        "ORDER BY question_embedding <=> %s::vector LIMIT 1",
        (str(embedding), str(embedding), threshold, str(embedding)),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return (row[0], round(row[1], 4)) if row else (None, None)


def store_semantic_cache(embedding: list[float], answer: str) -> None:
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO semantic_cache (question_embedding, answer) VALUES (%s::vector, %s)",
            (str(embedding), answer),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Failed to store semantic cache: {e}")
    finally:
        cur.close()
        conn.close()
