import os
import uuid
import json
import threading
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from backend.config import UPLOAD_DIR, BASE_DIR
from backend.models import init_db, get_db
from backend.ingestion import ingest_document
from backend.retrieval import chat

app = FastAPI(title="DAIMOND Platform")

@app.on_event("startup")
def startup():
    init_db()

class ChatRequest(BaseModel):
    question: str

@app.post("/api/chat")
async def api_chat(req: ChatRequest):
    result = await chat(req.question)
    return result

@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...)):
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ("pdf", "txt", "docx"):
        raise HTTPException(400, "Supported formats: PDF, TXT, DOCX")
    
    saved_name = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, saved_name)
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)
    
    db = get_db()
    cur = db.execute(
        "INSERT INTO documents (filename, original_name, file_type, file_size) VALUES (?, ?, ?, ?)",
        (saved_name, file.filename, ext, len(content))
    )
    doc_id = cur.lastrowid
    db.commit()
    db.close()
    
    # Process in background thread
    thread = threading.Thread(target=ingest_document, args=(doc_id, filepath, ext, file.filename))
    thread.start()
    
    return {"id": doc_id, "filename": file.filename, "status": "processing"}

@app.get("/api/documents")
def api_documents():
    db = get_db()
    rows = db.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()
    db.close()
    return [{"id": r["id"], "filename": r["original_name"], "file_type": r["file_type"],
             "file_size": r["file_size"], "chunk_count": r["chunk_count"],
             "status": r["status"], "created_at": r["created_at"]} for r in rows]

@app.get("/api/stats")
def api_stats():
    db = get_db()
    doc_count = db.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    chunk_count = db.execute("SELECT COALESCE(SUM(chunk_count),0) FROM documents").fetchone()[0]
    queries = db.execute("SELECT question, answer, sources, created_at FROM queries ORDER BY created_at DESC LIMIT 20").fetchall()
    db.close()
    return {
        "document_count": doc_count,
        "chunk_count": chunk_count,
        "recent_queries": [{"question": q["question"], "answer": q["answer"][:200],
                            "sources": q["sources"], "created_at": q["created_at"]} for q in queries]
    }

@app.delete("/api/documents/{doc_id}")
def api_delete_document(doc_id: int):
    db = get_db()
    doc = db.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    if not doc:
        raise HTTPException(404, "Document not found")
    filepath = os.path.join(UPLOAD_DIR, doc["filename"])
    if os.path.exists(filepath):
        os.remove(filepath)
    db.execute("DELETE FROM documents WHERE id=?", (doc_id,))
    db.commit()
    db.close()
    # Remove from chroma
    try:
        from backend.ingestion import get_chroma
        collection = get_chroma()
        # Delete all chunks for this doc
        existing = collection.get(where={"doc_id": doc_id})
        if existing["ids"]:
            collection.delete(ids=existing["ids"])
    except:
        pass
    return {"ok": True}

# Serve frontend
frontend_dir = os.path.join(BASE_DIR, "frontend")
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

@app.get("/")
def serve_index():
    return FileResponse(os.path.join(frontend_dir, "index.html"))
