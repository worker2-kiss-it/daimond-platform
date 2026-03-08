import os
import uuid
from pypdf import PdfReader
from docx import Document as DocxDocument
from backend.config import UPLOAD_DIR, CHROMA_DIR, CHUNK_SIZE, CHUNK_OVERLAP, EMBEDDING_MODEL
from backend.models import get_db
import chromadb
from chromadb.config import Settings

_chroma_client = None
_collection = None
_embedder = None

def get_chroma():
    global _chroma_client, _collection
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
        _collection = _chroma_client.get_or_create_collection("daimond_docs", metadata={"hnsw:space": "cosine"})
    return _collection

def get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer(EMBEDDING_MODEL)
    return _embedder

def extract_text(filepath: str, file_type: str) -> str:
    if file_type == "pdf":
        reader = PdfReader(filepath)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    elif file_type == "docx":
        doc = DocxDocument(filepath)
        return "\n".join(p.text for p in doc.paragraphs)
    elif file_type == "txt":
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    return ""

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
        i += chunk_size - overlap
    return chunks

def ingest_document(doc_id: int, filepath: str, file_type: str, original_name: str):
    try:
        text = extract_text(filepath, file_type)
        chunks = chunk_text(text)
        if not chunks:
            db = get_db()
            db.execute("UPDATE documents SET status='empty', chunk_count=0 WHERE id=?", (doc_id,))
            db.commit()
            db.close()
            return
        
        embedder = get_embedder()
        embeddings = embedder.encode(chunks).tolist()
        
        collection = get_chroma()
        ids = [f"doc{doc_id}_chunk{i}" for i in range(len(chunks))]
        metadatas = [{"doc_id": doc_id, "doc_name": original_name, "chunk_index": i} for i in range(len(chunks))]
        collection.add(ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas)
        
        db = get_db()
        db.execute("UPDATE documents SET status='ready', chunk_count=? WHERE id=?", (len(chunks), doc_id))
        db.commit()
        db.close()
    except Exception as e:
        db = get_db()
        db.execute("UPDATE documents SET status='error' WHERE id=?", (doc_id,))
        db.commit()
        db.close()
        raise e
