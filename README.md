

docker run --name postgres \
    -e POSTGRES_PASSWORD=************ \
    -p 5432:5432 \
    -d pgvector/pgvector:pg16

  CREATE EXTENSION vector;

   CREATE TABLE documents (
      id SERIAL PRIMARY KEY,
      filename VARCHAR(500),
      source_url TEXT,
      doc_type VARCHAR(50),        -- pdf, webpage, txt,
      created_at TIMESTAMP DEFAULT NOW()
  );

  -- Chunks with embeddings
  CREATE TABLE chunks (
      id SERIAL PRIMARY KEY,
      document_id INTEGER REFERENCES documents(id) ON
  DELETE CASCADE,
      chunk_index INTEGER,          -- order within the   document
      content TEXT NOT NULL,
      embedding vector(1536),
      metadata JSONB DEFAULT '{}',  -- page number,
      created_at TIMESTAMP DEFAULT NOW()
  );

  CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops);

  CREATE INDEX ON chunks (document_id);