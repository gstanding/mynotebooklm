from typing import List, Optional, Dict
from fastapi import FastAPI, Body, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import os

from .ingest import ingest_pdf, ingest_text_file, ingest_url, save_chunks, load_chunks, DATA_DIR
from .index import Index
from .hybrid import HybridIndex
from .rag import answer_query
from .notebooks import NotebookManager
from .sources import SourceManager

app = FastAPI(title="mynotebooklm", version="0.1.0")

app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

# 全局索引缓存：Dict[notebook_id, HybridIndex]
# key=None 代表默认的全局索引（旧兼容）
_INDEX_CACHE: Dict[Optional[str], HybridIndex] = {}


def get_index(notebook_id: Optional[str] = None) -> HybridIndex:
    global _INDEX_CACHE
    if notebook_id not in _INDEX_CACHE:
        chunks = load_chunks(notebook_id)
        _INDEX_CACHE[notebook_id] = HybridIndex(chunks)
    return _INDEX_CACHE[notebook_id]


def refresh_index(notebook_id: Optional[str] = None):
    global _INDEX_CACHE
    chunks = load_chunks(notebook_id)
    _INDEX_CACHE[notebook_id] = HybridIndex(chunks)


@app.get("/", response_class=HTMLResponse)
def home():
    with open(os.path.join(os.path.dirname(__file__), "static", "index.html"), "r", encoding="utf-8") as f:
        return f.read()


@app.get("/status")
def status(notebook_id: Optional[str] = None):
    chunks = load_chunks(notebook_id)
    return {"chunks": len(chunks), "data_dir": DATA_DIR, "notebook_id": notebook_id}


# --- Notebook Management ---

@app.get("/notebooks")
def list_notebooks():
    return NotebookManager.list_notebooks()


@app.post("/notebooks")
def create_notebook(title: str = Body(..., embed=True)):
    return NotebookManager.create_notebook(title)


@app.delete("/notebooks/{notebook_id}")
def delete_notebook(notebook_id: str):
    if NotebookManager.delete_notebook(notebook_id):
        # 清除缓存
        if notebook_id in _INDEX_CACHE:
            del _INDEX_CACHE[notebook_id]
        return {"success": True}
    raise HTTPException(status_code=404, detail="Notebook not found")


# --- Source Management ---

@app.get("/notebooks/{notebook_id}/sources")
def list_sources(notebook_id: str):
    return SourceManager.list_sources(notebook_id)

@app.delete("/notebooks/{notebook_id}/sources/{source_id:path}")
def delete_source(notebook_id: str, source_id: str):
    # source_id 可能包含 / 等字符（如果是 path/url），这里用 :path 匹配
    if SourceManager.delete_source(notebook_id, source_id):
        refresh_index(notebook_id)
        return {"success": True}
    raise HTTPException(status_code=404, detail="Source not found")

@app.patch("/notebooks/{notebook_id}/sources/{source_id:path}")
def update_source(notebook_id: str, source_id: str, enabled: bool = Body(..., embed=True)):
    if SourceManager.update_source(notebook_id, source_id, enabled=enabled):
        refresh_index(notebook_id)
        return {"success": True}
    raise HTTPException(status_code=404, detail="Source not found")


# --- Ingest & Query (Updated) ---

@app.post("/ingest")
def ingest(
    file_paths: List[str] = Body(default=[]),
    urls: List[str] = Body(default=[]),
    notebook_id: Optional[str] = Body(None),
):
    new_chunks = []
    for fp in file_paths:
        ext = os.path.splitext(fp)[1].lower()
        if ext in [".pdf"]:
            new_chunks.extend(ingest_pdf(fp))
        else:
            new_chunks.extend(ingest_text_file(fp))
    for u in urls:
        new_chunks.extend(ingest_url(u))
    
    stats = save_chunks(new_chunks, notebook_id=notebook_id)
    refresh_index(notebook_id)
    
    return {"ingested": stats, "new_chunks": len(new_chunks)}


@app.post("/query")
def query(
    q: str = Body(..., embed=True),
    top_k: int = Body(6, embed=True),
    notebook_id: Optional[str] = Body(None),
):
    index = get_index(notebook_id)
    result = answer_query(q, index, top_k=top_k)
    return result
