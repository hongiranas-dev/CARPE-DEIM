"""Small local Chroma retrieval pipeline with deterministic multilingual lexical vectors."""

import hashlib
import json
import math
import re
from pathlib import Path

import chromadb


ROOT = Path(__file__).resolve().parent
CORPUS_PATH = ROOT / "data" / "startup_sources.json"
CHROMA_PATH = ROOT / ".chroma"
COLLECTION_NAME = "founderos_startup_sources"
DIMENSIONS = 512
MIN_SIMILARITY = 0.12
_TOKEN_RE = re.compile(r"[\w]+", flags=re.UNICODE)
_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how", "i", "in", "is", "it",
    "of", "on", "or", "the", "to", "what", "when", "where", "which", "who", "with", "my", "me",
    "hai", "hain", "ka", "ke", "ki", "ko", "kya", "mein", "se", "ye", "aur", "hai", "hoga", "karein",
}


def _vector(text: str) -> list[float]:
    """Create normalized feature-hash vectors; no model download or external embedding key needed."""
    tokens = [token.lower() for token in _TOKEN_RE.findall(text) if token.lower() not in _STOP_WORDS]
    features = tokens + [f"{left}_{right}" for left, right in zip(tokens, tokens[1:])]
    values = [0.0] * DIMENSIONS
    for feature in features:
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "little") % DIMENSIONS
        sign = 1.0 if digest[4] & 1 else -1.0
        values[index] += sign
    norm = math.sqrt(sum(value * value for value in values))
    return [value / norm for value in values] if norm else values


def load_corpus(path: Path = CORPUS_PATH) -> list[dict]:
    documents = json.loads(path.read_text(encoding="utf-8"))
    required = {"id", "title", "publisher", "source_url", "text", "language", "passage_type"}
    for item in documents:
        if not required.issubset(item) or not item["source_url"].startswith("https://"):
            raise ValueError("Each corpus passage must include its source metadata and an HTTPS URL.")
    return documents


def get_collection():
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine", "description": "Curated official Indian startup guidance passages"},
    )
    documents = load_corpus()
    collection.upsert(
        ids=[item["id"] for item in documents],
        documents=[item["text"] for item in documents],
        embeddings=[_vector(item["text"]) for item in documents],
        metadatas=[{key: item[key] for key in ("title", "publisher", "source_url", "language", "passage_type")} for item in documents],
    )
    return collection


def retrieve(question: str, limit: int = 4) -> list[dict]:
    if not question.strip():
        return []
    result = get_collection().query(
        query_embeddings=[_vector(question)],
        n_results=min(limit, len(load_corpus())),
        include=["documents", "metadatas", "distances"],
    )
    passages = []
    for text, metadata, distance in zip(result["documents"][0], result["metadatas"][0], result["distances"][0]):
        similarity = 1.0 - float(distance)
        if similarity >= MIN_SIMILARITY:
            passages.append({"text": text, "similarity": similarity, **metadata})
    return passages


def has_sufficient_evidence(passages: list[dict]) -> bool:
    return bool(passages and passages[0]["similarity"] >= MIN_SIMILARITY)
