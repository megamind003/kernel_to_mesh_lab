import os
import pickle
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import OllamaEmbeddings
from langchain_core.documents import Document
from rank_bm25 import BM25Okapi
import numpy as np

from config import (
    CHROMA_DB_DIR, OLLAMA_BASE_URL, EMBEDDING_MODEL,
    BM25_INDEX_FILE, BM25_DOCS_FILE, TOP_K_RETRIEVAL, TOP_K_RERANK
)
from reranker import LocalReranker, RRFFusion
from graph import KnowledgeGraph

FAISS_INDEX_PATH = CHROMA_DB_DIR

class HybridRetriever:
    def __init__(self):
        print("Loading Vector Store (FAISS)...")
        self.embedding_function = OllamaEmbeddings(
            model=EMBEDDING_MODEL,
            base_url=OLLAMA_BASE_URL
        )
        try:
            self.vectorstore = FAISS.load_local(
                FAISS_INDEX_PATH, 
                self.embedding_function,
                allow_dangerous_deserialization=True
            )
        except Exception as e:
            print(f"Failed to load FAISS index: {e}")
            self.vectorstore = None
        
        print("Loading BM25 Index...")
        if os.path.exists(BM25_INDEX_FILE) and os.path.exists(BM25_DOCS_FILE):
            with open(BM25_INDEX_FILE, "rb") as f:
                self.bm25 = pickle.load(f)
            with open(BM25_DOCS_FILE, "rb") as f:
                self.bm25_docs = pickle.load(f)
        else:
            print("BM25 Index not found. Run ingestion first.")
            self.bm25 = None
            self.bm25_docs = []

        print("Loading Reranker...")
        self.reranker = LocalReranker()
        
        print("Loading Knowledge Graph...")
        self.kg = KnowledgeGraph()
        self.kg.load()

    def vector_search(self, query, k=TOP_K_RETRIEVAL):
        if not self.vectorstore:
            return []
        results = self.vectorstore.similarity_search_with_score(query, k=k)
        return [doc for doc, score in results]

    def keyword_search(self, query, k=TOP_K_RETRIEVAL):
        if not self.bm25:
            return []
        tokenized_query = query.split()
        docs = self.bm25.get_top_n(tokenized_query, self.bm25_docs, n=k)
        return docs

    def hybrid_search(self, query):
        vector_results = self.vector_search(query)
        keyword_results = self.keyword_search(query)
        
        fused_docs = RRFFusion.fuse([vector_results, keyword_results])
        
        reranked = self.reranker.rerank(query, fused_docs, top_k=TOP_K_RERANK)
        
        return reranked
