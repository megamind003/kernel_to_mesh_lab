import pandas as pd
import os
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from rank_bm25 import BM25Okapi
import pickle
import re

from config import (
    EMAILS_CSV_PATH, CHROMA_DB_DIR, OLLAMA_BASE_URL, EMBEDDING_MODEL,
    CHUNK_SIZE, CHUNK_OVERLAP, INGEST_LIMIT, BASE_DIR,
    BM25_INDEX_FILE, BM25_DOCS_FILE
)
from graph import KnowledgeGraph
from multimodal_parser import MultimodalParser

FAISS_INDEX_PATH = CHROMA_DB_DIR

def clean_text(text):
    if not isinstance(text, str):
        return ""
    return re.sub(r'\s+', ' ', text).strip()

def ingest_data():
    print(f"Loading data from {EMAILS_CSV_PATH}...")
    if not os.path.exists(EMAILS_CSV_PATH):
        print(f"Error: File not found at {EMAILS_CSV_PATH}")
        return

    try:
        df = pd.read_csv(EMAILS_CSV_PATH, nrows=INGEST_LIMIT)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    print(f"Loaded {len(df)} rows. Processing...")

    documents = []
    kg = KnowledgeGraph()
    
    multimodal_parser = MultimodalParser()
    print(f"Multimodal Parser: OCR={multimodal_parser.ocr_enabled}, Whisper={multimodal_parser.whisper_enabled}, Code={multimodal_parser.code_parser_enabled}")

    for index, row in df.iterrows():
        sender = row.get('From', '')
        receiver = row.get('To', '')
        date = row.get('Date', '')
        body = row.get('content', row.get('body', row.get('message', '')))
        
        text_content = f"From: {sender}\nTo: {receiver}\nDate: {date}\n\n{body}"
        cleaned_text = clean_text(text_content)
        
        if not cleaned_text:
            continue

        if isinstance(receiver, str):
            for r in receiver.split(','):
                r_clean = r.strip()
                if r_clean:
                    kg.add_email_interaction(sender, r_clean, date, "Email Interaction")

        documents.append(Document(
            page_content=cleaned_text,
            metadata={"source": "email", "sender": str(sender), "date": str(date)}
        ))

    print(f"Created {len(documents)} documents. Splitting...")

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP
    )
    splits = text_splitter.split_documents(documents)
    print(f"Generated {len(splits)} chunks.")

    print("Initializing Embeddings...")
    embedding_function = OllamaEmbeddings(
        model=EMBEDDING_MODEL,
        base_url=OLLAMA_BASE_URL
    )

    print("Persisting to FAISS...")
    vectorstore = FAISS.from_documents(
        documents=splits,
        embedding=embedding_function
    )
    vectorstore.save_local(FAISS_INDEX_PATH)
    print("Vector store created.")

    print("Building BM25 Index...")
    tokenized_corpus = [doc.page_content.split() for doc in splits]
    bm25 = BM25Okapi(tokenized_corpus)
    
    with open(BM25_INDEX_FILE, "wb") as f:
        pickle.dump(bm25, f)
    
    with open(BM25_DOCS_FILE, "wb") as f:
        pickle.dump(splits, f)
        
    print("BM25 Index saved.")

    kg.save()
    print("Ingestion Complete.")

if __name__ == "__main__":
    ingest_data()
