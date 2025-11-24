import os

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), "data_hardcore")
EMAILS_CSV_PATH = os.path.join(DATA_DIR, "emails.csv")
CHROMA_DB_DIR = os.path.join(BASE_DIR, "chroma_db")

# Models
OLLAMA_BASE_URL = "http://localhost:11434"
EMBEDDING_MODEL = "nomic-embed-text"
LLM_MODEL = "llama3.2:3b"
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# Ingestion
CHUNK_SIZE = 512
CHUNK_OVERLAP = 50
INGEST_LIMIT = 10000  # As per stress test protocol

# Retrieval
TOP_K_RETRIEVAL = 50
TOP_K_RERANK = 5

BM25_INDEX_FILE = os.path.join(BASE_DIR, "bm25_index.pkl")
BM25_DOCS_FILE = os.path.join(BASE_DIR, "bm25_docs.pkl")
