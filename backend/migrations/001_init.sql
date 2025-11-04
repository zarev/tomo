-- Initialize extensions and tables for TOMO PoC
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

-- Pets table
CREATE TABLE IF NOT EXISTS pets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now(),
  state JSONB DEFAULT '{}'
);

-- Memories table: small vector dim for PoC (64)
CREATE TABLE IF NOT EXISTS memories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pet_id UUID REFERENCES pets(id) ON DELETE CASCADE,
  embedding vector(64),
  content TEXT NOT NULL,
  category TEXT,
  importance SMALLINT DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- IVFFLAT index for approximate nearest neighbor (L2). Adjust lists for production.
CREATE INDEX IF NOT EXISTS memories_embedding_ivfflat ON memories USING ivfflat (embedding vector_l2_ops) WITH (lists = 100);
