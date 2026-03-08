import httpx
import json
from backend.config import LLM_BASE_URL, LLM_MODEL, LLM_API_KEY, TOP_K
from backend.ingestion import get_chroma, get_embedder
from backend.models import get_db

def search_documents(query: str, top_k: int = TOP_K):
    collection = get_chroma()
    embedder = get_embedder()
    query_embedding = embedder.encode([query]).tolist()
    results = collection.query(query_embeddings=query_embedding, n_results=top_k, include=["documents", "metadatas", "distances"])
    return results

async def chat(question: str) -> dict:
    results = search_documents(question)
    
    context_parts = []
    sources = []
    if results and results["documents"] and results["documents"][0]:
        for i, (doc, meta) in enumerate(zip(results["documents"][0], results["metadatas"][0])):
            context_parts.append(f"[Source {i+1}: {meta['doc_name']}]\n{doc}")
            if meta["doc_name"] not in sources:
                sources.append(meta["doc_name"])
    
    context = "\n\n".join(context_parts)
    
    system_prompt = """You are DAIMOND AI, a private enterprise AI assistant. Answer questions based on the provided context from uploaded documents. Always cite your sources. If the context doesn't contain relevant information, say so. Be concise and professional. You can answer in Hungarian or English based on the question language."""
    
    user_msg = f"Context from documents:\n{context}\n\nQuestion: {question}" if context else question
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{LLM_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {LLM_API_KEY}"},
                json={
                    "model": LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_msg}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 2000
                }
            )
            resp.raise_for_status()
            answer = resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        answer = f"LLM error: {str(e)}. Please check that the LLM proxy is running."
    
    # Log query
    db = get_db()
    db.execute("INSERT INTO queries (question, answer, sources) VALUES (?, ?, ?)",
               (question, answer, json.dumps(sources)))
    db.commit()
    db.close()
    
    return {"answer": answer, "sources": sources}
