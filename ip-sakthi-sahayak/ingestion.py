from haystack.document_stores.in_memory import InMemoryDocumentStore
from haystack import Document
from haystack.components.writers import DocumentWriter
from haystack_integrations.components.embedders.sentence_transformers import SentenceTransformersDocumentEmbedder
from haystack.components.preprocessors.document_splitter import DocumentSplitter
from haystack import Pipeline

from haystack.utils import ComponentDevice

from haystack.components.retrievers.in_memory import InMemoryBM25Retriever, InMemoryEmbeddingRetriever
from haystack_integrations.components.embedders.sentence_transformers import SentenceTransformersTextEmbedder
from haystack_integrations.components.rankers.sentence_transformers import SentenceTransformersSimilarityRanker

document_store = InMemoryDocumentStore()

docs = []
"""
 CREATION OF DOCUMENT OBJECT PART (PASS FOR NOW)
"""

document_splitter = DocumentSplitter(split_by="word", split_length=512, split_overlap=32)
document_embedder = SentenceTransformersDocumentEmbedder(
    model="sentence-transformers/all-MiniLM-L6-v2"
)
document_writer = DocumentWriter(document_store)

text_embedder = SentenceTransformersTextEmbedder(
    model="BAAI/bge-small-en-v1.5", device=ComponentDevice.from_str("cpu")
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

query = "apnea in infants"

result = hybrid_retrieval.run(
    {"text_embedder": {"text": query}, "bm25_retriever": {"query": query}, "ranker": {"query": query}}
)

for doc in result["ranker"]["documents"]:
    print(doc.meta["title"], "\t", doc.score)
    print(doc.meta["abstract"])
    print("\n")
