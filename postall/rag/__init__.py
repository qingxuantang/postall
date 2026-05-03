"""
PostAll RAG Module - Semantic retrieval for content generation

Uses historical high-scoring content as few-shot examples during generation.
Built on ChromaDB with local embeddings (all-MiniLM-L6-v2, zero API cost).

The embedding model (~80MB) is downloaded automatically on first use.
"""
