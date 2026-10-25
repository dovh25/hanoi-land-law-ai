import logging
from typing import Optional, Dict, List, Any
import json
import pickle as pkl
from tqdm import tqdm  # Import progress bar
import uuid

# LangChain Imports
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_core.documents import Document

from qdrant_client.http.models import Distance, VectorParams
from qdrant_client.models import PointStruct
from qdrant_client import QdrantClient
from backend.core.config import Config as RuntimeConfig
from backend.core.index_safety import prepare_collection, destructive_cli_args

logger = logging.getLogger(__name__)




class Config(RuntimeConfig):
    APP_NAME: str = "Vietnamese Law API"
    API_STR: str = "/api/v1"
    SERVER_HOST: str = "http://localhost:8000"
    PROJECT_NAME: str = "vietnamese-law-api"
    MODEL: str = "gemini-2.5-flash-lite"
    QDRANT_PORT: int = 6333
    CHUNK_SIZE: int = 1024
    COLLECTION_NAME: str = f"laws"
    EMBEDDINGS_FILE: str = f"data/processed_chunksize_{CHUNK_SIZE}_alibaba/embeddings.pkl"
    DOCS_FILE: str = f"data/processed_chunksize_{CHUNK_SIZE}_alibaba/documents.json"


config = Config()


def _read_embeddings_from_pkl(input_file):
    with open(input_file, "rb") as f:
        embeddings = pkl.load(f)
    return embeddings


def _load_docs_from_json(input_file):
    with open(input_file, "r", encoding="utf-8") as f:
        json_docs = json.load(f)
        docs = [Document(**doc) for doc in json_docs]
    return docs


def ingest_data(*, recreate=False, confirm_collection=None) -> None:
    """
    Ingest new documents into Qdrant.
    Each document should be a dict with 'content' and 'metadata' keys.
    """
    client = QdrantClient(host=config.QDRANT_HOST, port=config.QDRANT_PORT)
    collection_name = config.COLLECTION_NAME

    prepare_collection(client, collection_name, recreate=recreate, confirm_collection=confirm_collection)

    # Prepare data for upsert
    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
    )

    docs = _load_docs_from_json(config.DOCS_FILE)
    embeddings = _read_embeddings_from_pkl(config.EMBEDDINGS_FILE)

    # Configuration
    BATCH_SIZE = 128  # 64-128 is usually the sweet spot for network/speed

    # Calculate total for progress bar
    total_docs = len(docs)

    # Loop through data in chunks
    for i in tqdm(range(0, total_docs, BATCH_SIZE), desc="Uploading to Qdrant"):

        # 1. Slice the current batch
        batch_docs = docs[i : i + BATCH_SIZE]
        batch_vecs = embeddings[i : i + BATCH_SIZE]

        # 2. Build points using List Comprehension (faster than .append loops)
        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={"page_content": doc.page_content, "metadata": doc.metadata},
            )
            for doc, vector in zip(batch_docs, batch_vecs)
        ]

        # 3. Upsert the batch
        # wait=False significantly speeds up ingestion by not blocking for disk sync
        client.upsert(collection_name=collection_name, points=points, wait=False)
    logger.info("Data ingestion to Qdrant completed.")


if __name__ == "__main__":
    ingest_data(**destructive_cli_args())
