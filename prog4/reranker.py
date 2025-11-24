import numpy as np
from typing import List, Tuple
from langchain_core.documents import Document
from langchain_community.embeddings import OllamaEmbeddings
from config import OLLAMA_BASE_URL, EMBEDDING_MODEL


class LocalReranker:
    """Lightweight reranking using cosine similarity with embeddings."""
    
    def __init__(self):
        self.embedder = OllamaEmbeddings(
            model=EMBEDDING_MODEL,
            base_url=OLLAMA_BASE_URL
        )
    
    def rerank(self, query: str, documents: List[Document], top_k: int = 5) -> List[Document]:
        if not documents:
            return []
        
        query_embedding = self.embedder.embed_query(query)
        doc_texts = [doc.page_content for doc in documents]
        doc_embeddings = self.embedder.embed_documents(doc_texts)
        
        scores = []
        for doc_emb in doc_embeddings:
            score = self._cosine_similarity(query_embedding, doc_emb)
            scores.append(score)
        
        scored_docs = list(zip(documents, scores))
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        
        return [doc for doc, score in scored_docs[:top_k]]
    
    @staticmethod
    def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        vec1_np = np.array(vec1)
        vec2_np = np.array(vec2)
        
        dot_product = np.dot(vec1_np, vec2_np)
        norm1 = np.linalg.norm(vec1_np)
        norm2 = np.linalg.norm(vec2_np)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))


class RRFFusion:
    """Reciprocal Rank Fusion for combining multiple ranked lists."""
    
    @staticmethod
    def fuse(ranked_lists: List[List[Document]], k: int = 60) -> List[Document]:
        if not ranked_lists:
            return []
        
        scores = {}
        
        for ranked_list in ranked_lists:
            for rank, doc in enumerate(ranked_list, start=1):
                doc_id = id(doc)
                if doc_id not in scores:
                    scores[doc_id] = {"doc": doc, "score": 0.0}
                scores[doc_id]["score"] += 1.0 / (k + rank)
        
        sorted_docs = sorted(scores.values(), key=lambda x: x["score"], reverse=True)
        return [item["doc"] for item in sorted_docs]
