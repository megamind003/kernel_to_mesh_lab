import ollama
from config import LLM_MODEL

class LLMInterface:
    def __init__(self):
        self.model = LLM_MODEL

    def generate_answer(self, query, context_docs):
        """Generates an answer using the local LLM."""
        
        context_text = "\n\n".join([doc.page_content for doc in context_docs])
        
        prompt = f"""You are CORTEX, an intelligent offline assistant.
Use the following context to answer the user's question.
If the answer is not in the context, say you don't know.
Be precise and concise.

Context:
{context_text}

Question: {query}

Answer:"""

        print(f"Generating answer with {self.model}...")
        
        stream = ollama.chat(
            model=self.model,
            messages=[{'role': 'user', 'content': prompt}],
            stream=True,
        )

        full_response = ""
        for chunk in stream:
            content = chunk['message']['content']
            print(content, end='', flush=True)
            full_response += content
        
        print("\n")
        return full_response
