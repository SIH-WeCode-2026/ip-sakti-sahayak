from haystack.document_stores.in_memory import InMemoryDocumentStore
from haystack import Document
from haystack.components.writers import DocumentWriter
from haystack_integrations.components.embedders.sentence_transformers import SentenceTransformersDocumentEmbedder
from haystack.components.preprocessors.document_splitter import DocumentSplitter
from haystack import Pipeline
from haystack.components.retrievers.in_memory import InMemoryBM25Retriever, InMemoryEmbeddingRetriever
from haystack_integrations.components.embedders.sentence_transformers import SentenceTransformersTextEmbedder
from haystack_integrations.components.rankers.sentence_transformers import SentenceTransformersSimilarityRanker
import google.generativeai as genai
import os

from utils.pdf_to_text import load_all_pdfs, FILENAME_MAP

document_store = InMemoryDocumentStore()

pdf_paths = list(FILENAME_MAP.keys())

pdf_texts = load_all_pdfs(pdf_paths)

docs = []
for name, text in pdf_texts.items():
    docs.append(Document(content=text, meta={"filename": name}))

document_splitter = DocumentSplitter(split_by="word", split_length=512, split_overlap=32)
document_embedder = SentenceTransformersDocumentEmbedder(
    model="sentence-transformers/all-MiniLM-L6-v2"
)
document_writer = DocumentWriter(document_store)

text_embedder = SentenceTransformersTextEmbedder(
    model="sentence-transformers/all-MiniLM-L6-v2"
)
embedding_retriever = InMemoryEmbeddingRetriever(document_store)
bm25_retriever = InMemoryBM25Retriever(document_store)

indexing_pipeline = Pipeline()
indexing_pipeline.add_component("document_splitter", document_splitter)
indexing_pipeline.add_component("document_embedder", document_embedder)
indexing_pipeline.add_component("document_writer", document_writer)

indexing_pipeline.connect("document_splitter", "document_embedder")
indexing_pipeline.connect("document_embedder", "document_writer")

indexing_pipeline.run({"document_splitter": {"documents": docs}})


ranker = SentenceTransformersSimilarityRanker(model="BAAI/bge-reranker-base")

hybrid_retrieval = Pipeline()
hybrid_retrieval.add_component("text_embedder", text_embedder)
hybrid_retrieval.add_component("embedding_retriever", embedding_retriever)
hybrid_retrieval.add_component("bm25_retriever", bm25_retriever)
hybrid_retrieval.add_component("ranker", ranker)

hybrid_retrieval.connect("text_embedder", "embedding_retriever")
hybrid_retrieval.connect("bm25_retriever", "ranker")
hybrid_retrieval.connect("embedding_retriever", "ranker")


genai.configure(api_key=os.environ["GOOGLE_API_KEY"] if "GOOGLE_API_KEY" in os.environ else None)

model = genai.GenerativeModel("gemini-3.1-flash-lite")


def build_prompt(query, docs):
    context = "\n\n---\n\n".join(
        f"[Source: {d.meta.get('filename', 'unknown')}]\n{d.content}"
        for d in docs
    )
    return f"""You are a legal/regulatory assistant answering questions about Ayurvedic IP and drug regulation in India.

Use ONLY the context below to answer the question. Cite the source filename when making a claim. If the context doesn't contain enough information, say so clearly instead of guessing.

CONTEXT:
{context}

QUESTION:
{query}

Give a detailed, well-structured answer."""


print("\nReady. Type a query (or 'exit' to quit):")
while True:
    query = input("\n> ").strip()
    if query.lower() in ("exit", "quit"):
        break
    if not query:
        continue

    result = hybrid_retrieval.run(
        {"text_embedder": {"text": query}, "bm25_retriever": {"query": query}, "ranker": {"query": query}}
    )

    top_docs = result["ranker"]["documents"][:10]

    try:
        prompt = build_prompt(query, top_docs)
        response = model.generate_content(prompt)
        print("\n--- ANSWER ---\n")
        print(response.text)
    except Exception as e:
        print(f"\n[LLM call failed: {e}]")
        print("--- Falling back to retrieved chunks ---\n")
        for i, doc in enumerate(top_docs, start=1):
            print(f"[{i}] Source: {doc.meta.get('filename', 'unknown')} (score: {doc.score:.3f})")
            print(doc.content[:400])
            print()


