import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
from dotenv import load_dotenv

from haystack.document_stores.in_memory import InMemoryDocumentStore
from haystack import Document, Pipeline
from haystack.components.writers import DocumentWriter
from haystack_integrations.components.embedders.sentence_transformers import (
    SentenceTransformersDocumentEmbedder,
    SentenceTransformersTextEmbedder
)
from haystack.components.retrievers.in_memory import InMemoryBM25Retriever, InMemoryEmbeddingRetriever
from haystack_integrations.components.rankers.sentence_transformers import SentenceTransformersSimilarityRanker
from haystack.utils import ComponentDevice

load_dotenv()

app = FastAPI(title="IP-SAKTI API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

document_store = InMemoryDocumentStore()
hybrid_retrieval = Pipeline()
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY", "mock_key"))

@app.on_event("startup")
async def load_and_index_data():
    """Runs once when the server starts to load Ayush data into memory."""
    print("Loading Models and Indexing Ayush Documents...")
    
    ayush_docs = [
        Document(
            content="An invention which in effect is traditional knowledge or which is an aggregation or duplication of known properties of traditionally known component or components is not patentable.",
            meta={"act": "Indian Patents Act, 1970", "section": "Section 3(p)"}
        ),
        Document(
            content="No person who is a citizen of India shall obtain any biological resource for commercial utilization without prior intimation to the State Biodiversity Board. Local vaids and hakims are exempt.",
            meta={"act": "Biological Diversity Act", "section": "Section 7"}
        )
    ]

    document_embedder = SentenceTransformersDocumentEmbedder(
        model="BAAI/bge-small-en-v1.5", device=ComponentDevice.from_str("cpu")
    )
    document_writer = DocumentWriter(document_store)

    indexing_pipeline = Pipeline()
    indexing_pipeline.add_component("document_embedder", document_embedder)
    indexing_pipeline.add_component("document_writer", document_writer)
    indexing_pipeline.connect("document_embedder", "document_writer")
    indexing_pipeline.run({"document_embedder": {"documents": ayush_docs}})

    text_embedder = SentenceTransformersTextEmbedder(
        model="BAAI/bge-small-en-v1.5", device=ComponentDevice.from_str("cpu")
    )
    embedding_retriever = InMemoryEmbeddingRetriever(document_store)
    bm25_retriever = InMemoryBM25Retriever(document_store)
    ranker = SentenceTransformersSimilarityRanker(model="BAAI/bge-reranker-base")

    hybrid_retrieval.add_component("text_embedder", text_embedder)
    hybrid_retrieval.add_component("embedding_retriever", embedding_retriever)
    hybrid_retrieval.add_component("bm25_retriever", bm25_retriever)
    hybrid_retrieval.add_component("ranker", ranker)

    hybrid_retrieval.connect("text_embedder", "embedding_retriever")
    hybrid_retrieval.connect("bm25_retriever", "ranker")
    hybrid_retrieval.connect("embedding_retriever", "ranker")
    print("Indexing Complete! API is ready.")

class QueryRequest(BaseModel):
    question: str
    jurisdiction: str
    category: str

@app.post("/query")
async def execute_query(req: QueryRequest):
    
    result = hybrid_retrieval.run(
        {
            "text_embedder": {"text": req.question}, 
            "bm25_retriever": {"query": req.question}, 
            "ranker": {"query": req.question}
        }
    )
    
    retrieved_docs = result["ranker"]["documents"]
    
    context_text = "\n\n".join(
        [f"Source: {doc.meta.get('act')} {doc.meta.get('section')}\nText: {doc.content}" for doc in retrieved_docs]
    )
    
    system_prompt = f"You are IP-SAKTI Sahayak. Base your answer EXCLUSIVELY on this Legal Context:\n\n{context_text}"

    chat_completion = groq_client.chat.completions.create(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": req.question}
        ],
        model="llama-3.3-70b-versatile",
        temperature=0.1
    )
    
    formatted_citations = [
        {"source": f"{doc.meta.get('act', 'Unknown')} {doc.meta.get('section', '')}", "text_chunk": doc.content}
        for doc in retrieved_docs
    ]
    
    return {
        "answer": chat_completion.choices[0].message.content,
        "citations": formatted_citations,
        "confidence_score": 95.0
    }