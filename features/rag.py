"""
RAG mémoire sémantique — 100% gratuit, tourne en local.

- Embeddings : sentence-transformers (all-MiniLM-L6-v2, 22M params, offline)
- Vector store : ChromaDB persistent (fichier local)
- Pas de clé API, pas de coût, pas de requête réseau après le premier téléchargement du modèle.
"""
import hashlib
import os
from datetime import datetime


_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB_PATH = os.path.join(_BASE_DIR, "rag_db")
_COLLECTION_NAME = "memory"
_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

_client = None
_collection = None
_model = None


def _get_collection():
    """Initialise paresseusement ChromaDB et le modèle d'embedding."""
    global _client, _collection, _model
    if _collection is not None:
        return _collection
    try:
        import chromadb
        from chromadb.config import Settings
    except ImportError:
        raise RuntimeError("chromadb non installé. Exécute : pip install chromadb sentence-transformers")

    _client = chromadb.PersistentClient(
        path=_DB_PATH,
        settings=Settings(anonymized_telemetry=False),
    )
    _collection = _client.get_or_create_collection(
        name=_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    return _collection


def _get_model():
    global _model
    if _model is not None:
        return _model
    from sentence_transformers import SentenceTransformer
    _model = SentenceTransformer(_MODEL_NAME)
    return _model


def _embed(texts: list[str]) -> list[list[float]]:
    model = _get_model()
    return model.encode(texts, show_progress_bar=False, convert_to_numpy=True).tolist()


def _doc_id(source: str, content: str, timestamp: str = "") -> str:
    """ID stable basé sur hash du contenu + source."""
    h = hashlib.md5(f"{source}|{timestamp}|{content}".encode()).hexdigest()
    return f"{source}_{h[:16]}"


def index_documents(documents: list[dict], force: bool = False) -> int:
    """
    Indexe une liste de documents, en SKIPPANT ceux déjà indexés (delta-indexing).
    Format attendu :
    [{"content": str, "source": str, "timestamp": str, "metadata": dict}, ...]

    force=True : réindexe même les documents déjà présents (utile pour migration).

    Retourne le nombre de documents RÉELLEMENT ajoutés (après déduplication).
    """
    if not documents:
        return 0
    col = _get_collection()

    # 1) Calculer les IDs candidats
    candidates: list[tuple[str, str, dict]] = []
    for doc in documents:
        content = doc.get("content", "").strip()
        if not content or len(content) < 10:
            continue
        source = doc.get("source", "unknown")
        timestamp = doc.get("timestamp", "")
        doc_id = _doc_id(source, content, timestamp)
        meta = {
            "source": source,
            "timestamp": timestamp,
            "indexed_at": datetime.now().isoformat(timespec="seconds"),
        }
        meta.update(doc.get("metadata", {}))
        candidates.append((doc_id, content[:1500], meta))

    if not candidates:
        return 0

    # 2) Delta : ne garder que les IDs absents de la collection
    if not force:
        existing = set()
        batch_size = 100
        for i in range(0, len(candidates), batch_size):
            batch_ids = [c[0] for c in candidates[i:i + batch_size]]
            try:
                result = col.get(ids=batch_ids)
                existing.update(result.get("ids", []))
            except Exception:
                pass
        candidates = [c for c in candidates if c[0] not in existing]

    if not candidates:
        return 0

    # 3) Encoder seulement les nouveaux documents et upsert
    ids = [c[0] for c in candidates]
    contents = [c[1] for c in candidates]
    metadatas = [c[2] for c in candidates]

    embeddings = _embed(contents)
    col.upsert(ids=ids, embeddings=embeddings, documents=contents, metadatas=metadatas)
    return len(candidates)


def search_memory(query: str, top_k: int = 5, source_filter: str = None) -> list[dict]:
    """
    Recherche sémantique dans la mémoire indexée.
    Retourne les top_k chunks les plus pertinents.
    """
    try:
        col = _get_collection()
        if col.count() == 0:
            return []
        query_embedding = _embed([query])[0]
        where = {"source": source_filter} if source_filter else None
        results = col.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, col.count()),
            where=where,
        )
        out = []
        for i in range(len(results["ids"][0])):
            out.append({
                "content": results["documents"][0][i],
                "source": results["metadatas"][0][i].get("source", ""),
                "timestamp": results["metadatas"][0][i].get("timestamp", ""),
                "relevance": round(1 - results["distances"][0][i], 3),
            })
        return out
    except Exception as e:
        return [{"error": str(e)}]


def get_stats() -> dict:
    try:
        col = _get_collection()
        count = col.count()
        return {"total_chunks": count, "db_path": _DB_PATH, "model": _MODEL_NAME}
    except Exception as e:
        return {"error": str(e)}


def clear_memory() -> str:
    """Vide la mémoire sémantique (utile pour reset)."""
    try:
        global _collection, _client
        if _client is None:
            _get_collection()
        _client.delete_collection(_COLLECTION_NAME)
        _collection = None
        return "Mémoire sémantique effacée."
    except Exception as e:
        return f"Erreur : {e}"
