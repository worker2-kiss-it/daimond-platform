# DAIMOND — Private AI Platform

Enterprise-grade private AI platform for document intelligence.

## Features
- Document upload (PDF, TXT, DOCX) with automatic chunking and embedding
- RAG-powered chat with source citations
- ChromaDB vector search
- Admin dashboard

## Setup
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m uvicorn backend.main:app --port 8005
```

Visit http://localhost:8005
