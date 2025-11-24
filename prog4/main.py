import argparse
import time
import sys
from ingest import ingest_data
from retrieval import HybridRetriever
from llm_interface import LLMInterface

def main():
    parser = argparse.ArgumentParser(description="CORTEX: The Neural Extension OS")
    parser.add_argument("--ingest", action="store_true", help="Ingest data from emails.csv")
    parser.add_argument("--query", type=str, help="Query the system")
    
    args = parser.parse_args()

    if args.ingest:
        start_time = time.time()
        print("Starting Ingestion...")
        ingest_data()
        print(f"Ingestion finished in {time.time() - start_time:.2f} seconds.")

    if args.query:
        print(f"Query: {args.query}")
        
        # Retrieval
        start_retrieval = time.time()
        retriever = HybridRetriever()
        docs = retriever.hybrid_search(args.query)
        retrieval_time = time.time() - start_retrieval
        
        print(f"Retrieval took {retrieval_time*1000:.2f} ms")
        
        if not docs:
            print("No relevant documents found.")
            return

        # Generation
        llm = LLMInterface()
        answer = llm.generate_answer(args.query, docs)
        
        # print(f"\nAnswer: {answer}") # Already printed by stream

if __name__ == "__main__":
    main()
