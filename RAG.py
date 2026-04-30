import os
import tempfile
import time
from functools import lru_cache
from typing import Any

import requests
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from langchain.chains import RetrievalQA
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.llms import Ollama
from langchain_community.vectorstores import FAISS
from pydantic import BaseModel


OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

app = FastAPI(title="Ledger PDF QA API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://192.168.1.7:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

workspace: dict[str, Any] = {
    "doc_name": None,
    "pdf_bytes": None,
    "pages": [],
    "chunks": [],
    "chain": None,
    "settings": None,
    "last_indexed_seconds": None,
}


class ChatRequest(BaseModel):
    query: str


class SettingsRequest(BaseModel):
    modelName: str = "llama3"
    topK: int = 4
    chunkSize: int = 900
    chunkOverlap: int = 120


def reset_workspace() -> None:
    workspace.update(
        {
            "doc_name": None,
            "pdf_bytes": None,
            "pages": [],
            "chunks": [],
            "chain": None,
            "settings": None,
            "last_indexed_seconds": None,
        }
    )


@lru_cache(maxsize=1)
def load_embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")


def format_source(doc: Any) -> dict[str, Any]:
    raw_page = doc.metadata.get("page")
    page = raw_page + 1 if isinstance(raw_page, int) else raw_page or "N/A"
    return {
        "page": page,
        "label": f"Retrieved from page {page}",
        "content": doc.page_content,
    }


def public_state() -> dict[str, Any]:
    return {
        "docName": workspace["doc_name"],
        "pages": len(workspace["pages"]),
        "chunks": len(workspace["chunks"]),
        "settings": workspace["settings"],
        "indexedSeconds": workspace["last_indexed_seconds"],
        "hasDocument": bool(workspace["pdf_bytes"]),
    }


def ollama_health() -> dict[str, Any]:
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2)
        response.raise_for_status()
        data = response.json()
        return {
            "ok": True,
            "baseUrl": OLLAMA_BASE_URL,
            "models": [model.get("name") for model in data.get("models", [])],
        }
    except requests.exceptions.RequestException as exc:
        return {
            "ok": False,
            "baseUrl": OLLAMA_BASE_URL,
            "message": (
                "Ollama is not reachable. Start it with `ollama serve`, then "
                "make sure the selected model is pulled locally."
            ),
            "detail": str(exc),
        }


def build_qa_system(
    pdf_bytes: bytes,
    chunk_size: int,
    chunk_overlap: int,
    top_k: int,
    model_name: str,
):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(pdf_bytes)
        temp_path = tmp.name

    try:
        pages = PyPDFLoader(temp_path).load()
    finally:
        os.unlink(temp_path)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    chunks = splitter.split_documents(pages)
    vectordb = FAISS.from_documents(chunks, load_embeddings())
    llm = Ollama(model=model_name, base_url=OLLAMA_BASE_URL)
    chain = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=vectordb.as_retriever(search_kwargs={"k": top_k}),
        return_source_documents=True,
    )
    return pages, chunks, chain


def index_workspace_pdf(
    *,
    pdf_bytes: bytes,
    doc_name: str,
    model_name: str,
    top_k: int,
    chunk_size: int,
    chunk_overlap: int,
) -> dict[str, Any]:
    start_time = time.time()
    pages, chunks, chain = build_qa_system(
        pdf_bytes=pdf_bytes,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        top_k=top_k,
        model_name=model_name,
    )
    workspace.update(
        {
            "doc_name": doc_name,
            "pdf_bytes": pdf_bytes,
            "pages": pages,
            "chunks": chunks,
            "chain": chain,
            "settings": {
                "modelName": model_name,
                "topK": top_k,
                "chunkSize": chunk_size,
                "chunkOverlap": chunk_overlap,
            },
            "last_indexed_seconds": round(time.time() - start_time, 2),
        }
    )
    return public_state()


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"api": "ok", "ollama": ollama_health()}


@app.get("/api/state")
def state() -> dict[str, Any]:
    return public_state()


@app.post("/api/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    model_name: str = Form("llama3"),
    top_k: int = Form(4),
    chunk_size: int = Form(900),
    chunk_overlap: int = Form(120),
) -> dict[str, Any]:
    filename = file.filename or "uploaded.pdf"
    is_pdf_type = file.content_type in {
        "application/pdf",
        "application/x-pdf",
        "application/octet-stream",
    }
    is_pdf_name = filename.lower().endswith(".pdf")
    if not (is_pdf_type or is_pdf_name):
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="The uploaded PDF is empty.")

    try:
        indexed_state = index_workspace_pdf(
            pdf_bytes=pdf_bytes,
            doc_name=filename,
            model_name=model_name,
            top_k=top_k,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not index the PDF: {exc}",
        ) from exc

    return {
        **indexed_state,
        "message": (
            f"I've indexed {filename} and I'm ready. Ask for a summary, "
            "definitions, comparisons, or citations."
        ),
    }


@app.post("/api/apply-settings")
def apply_settings(request: SettingsRequest) -> dict[str, Any]:
    if not workspace["pdf_bytes"]:
        raise HTTPException(
            status_code=400,
            detail="Upload a PDF before applying retrieval settings.",
        )

    try:
        indexed_state = index_workspace_pdf(
            pdf_bytes=workspace["pdf_bytes"],
            doc_name=workspace["doc_name"] or "uploaded.pdf",
            model_name=request.modelName,
            top_k=request.topK,
            chunk_size=request.chunkSize,
            chunk_overlap=request.chunkOverlap,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not apply settings: {exc}",
        ) from exc

    return {
        **indexed_state,
        "message": (
            "Applied the control room settings and rebuilt the document index "
            f"with {request.topK} chunks retrieved per question."
        ),
    }


@app.get("/api/pdf")
def pdf_preview() -> Response:
    if not workspace["pdf_bytes"]:
        raise HTTPException(status_code=404, detail="No PDF has been uploaded yet.")
    return Response(content=workspace["pdf_bytes"], media_type="application/pdf")


@app.get("/api/chunks")
def chunks() -> dict[str, Any]:
    return {
        "chunks": [
            {
                "index": index,
                "page": format_source(chunk)["page"],
                "content": chunk.page_content,
            }
            for index, chunk in enumerate(workspace["chunks"][:25], start=1)
        ]
    }


@app.post("/api/chat")
def chat(request: ChatRequest) -> dict[str, Any]:
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Ask a question first.")
    if not workspace["chain"]:
        raise HTTPException(status_code=400, detail="Upload and index a PDF first.")

    try:
        response = workspace["chain"].invoke({"query": query})
    except requests.exceptions.ConnectionError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Ollama is not running on localhost:11434. Start it with "
                "`ollama serve`, then run `ollama pull "
                f"{workspace['settings']['modelName']}` if needed."
            ),
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Ollama request failed: {exc}",
        ) from exc

    return {
        "answer": response["result"],
        "sources": [
            format_source(doc) for doc in response.get("source_documents", [])
        ],
    }


@app.post("/api/reset")
def reset() -> dict[str, Any]:
    reset_workspace()
    return public_state()
