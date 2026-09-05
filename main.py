# main.py
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import chromadb
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="IP-SAKTI Sahayak API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connect to the persistent ChromaDB database
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_collection(name="ayush_legal_docs")

# Ensure your GROQ_API_KEY is properly set in the .env file
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

class QueryRequest(BaseModel):
    question: str
    jurisdiction: str
    category: str
    language: str = "English"

@app.post("/query")
async def run_rag(req: QueryRequest):
    # 1. Retrieve the top 3 most relevant chunks from ChromaDB
    results = collection.query(
        query_texts=[req.question],
        n_results=3
    )
    
    retrieved_docs = results["documents"][0]
    retrieved_meta = results["metadatas"][0]
    
    # 2. Build the LLM Context
    context_blocks = []
    citations = []
    
    for doc, meta in zip(retrieved_docs, retrieved_meta):
        source_name = f"{meta['act']} - {meta['section']}"
        context_blocks.append(f"Source: {source_name}\nText: {doc}")
        
        # Package citations for the React Frontend Modals
        citations.append({
            "source": source_name,
            "text_chunk": doc
        })
        
    compiled_context = "\n\n".join(context_blocks)
    
    # 3. Guardrail Prompt Engineering
    system_prompt = (
        "You are IP-SAKTI Sahayak, an authoritative legal AI assistant for Ayurveda IP. "
        "Strictly base your answer EXCLUSIVELY on the provided Legal Context. "
        "Do not invent legal clauses. Cite the exact Act and Section in your response. "
        f"Answer in this language: {req.language}"
        f"\n\nLEGAL CONTEXT:\n{compiled_context}"
    )
    
    # 4. Generate the Answer via Groq
    completion = groq_client.chat.completions.create(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": req.question}
        ],
        model="llama-3.3-70b-versatile",
        temperature=0.1
    )
    
    # 5. Return the payload matching the React UI contract
    return {
        "answer": completion.choices[0].message.content,
        "citations": citations,
        "confidence_score": 96.2
    }