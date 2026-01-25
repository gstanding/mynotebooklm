import json
import os
from typing import Dict, List, Optional
import requests
from bs4 import BeautifulSoup
from readability import Document
from PyPDF2 import PdfFileReader
from .utils import clean_text, chunk_text
import asyncio
from pyppeteer import launch

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
CHUNKS_PATH = os.path.join(DATA_DIR, "chunks.json")


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _add_chunks(all_chunks: List[Dict], source_id: str, source_type: str, text: str, location: Optional[str] = None, url: Optional[str] = None, path: Optional[str] = None):
    text = clean_text(text)
    for chunk in chunk_text(text):
        all_chunks.append(
            {
                "id": f"{source_id}#{len(all_chunks)}",
                "text": chunk,
                "source_id": source_id,
                "source_type": source_type,
                "location": location,
                "url": url,
                "path": path,
            }
        )


def ingest_pdf(file_path: str, source_id: Optional[str] = None) -> List[Dict]:
    ensure_data_dir()
    source_id = source_id or os.path.basename(file_path)
    chunks: List[Dict] = []
    
    try:
        # PyPDF2 1.x 的 PdfFileReader 需要保持文件打开状态，直到读取完成
        with open(file_path, "rb") as f:
            reader = PdfFileReader(f)
            num_pages = reader.getNumPages()
            for i in range(num_pages):
                try:
                    page = reader.getPage(i)
                    text = page.extractText() or ""
                    if text.strip():
                        _add_chunks(chunks, source_id, "pdf", text, location=f"page {i+1}", path=file_path)
                except Exception as e:
                    print(f"Error reading page {i} of {file_path}: {e}")
                    continue
    except Exception as e:
        print(f"Error opening PDF {file_path}: {e}")
        
    return chunks


def ingest_text_file(file_path: str, source_id: Optional[str] = None) -> List[Dict]:
    ensure_data_dir()
    source_id = source_id or os.path.basename(file_path)
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()
    chunks: List[Dict] = []
    _add_chunks(chunks, source_id, "text", text, path=file_path)
    return chunks


def _get_html_via_requests(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
    }
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    return resp.text


import shutil

async def _get_html_via_pyppeteer(url: str) -> str:
    # 使用项目内的临时目录作为 userDataDir，避免权限问题
    user_data_dir = os.path.join(DATA_DIR, "pyppeteer_data")
    if os.path.exists(user_data_dir):
        shutil.rmtree(user_data_dir, ignore_errors=True)
    os.makedirs(user_data_dir, exist_ok=True)
    
    browser = await launch(
        handleSIGINT=False,
        handleSIGTERM=False,
        handleSIGHUP=False,
        headless=True,
        userDataDir=user_data_dir,
        args=["--no-sandbox", "--disable-setuid-sandbox"]
    )
    page = await browser.newPage()
    await page.setUserAgent("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36")
    try:
        await page.goto(url, {"waitUntil": "networkidle2", "timeout": 60000})
        content = await page.content()
    finally:
        await browser.close()
        # 清理临时目录
        if os.path.exists(user_data_dir):
            shutil.rmtree(user_data_dir, ignore_errors=True)
    return content


def ingest_url(url: str, source_id: Optional[str] = None) -> List[Dict]:
    ensure_data_dir()
    print(f"DEBUG: Starting ingest for {url}")
    
    html = ""
    try:
        # 1. 尝试 requests
        html = _get_html_via_requests(url)
        # 简单的检查：如果内容太短，可能是 SPA 或反爬，转用 Pyppeteer
        if len(html) < 500 or "<script" in html[:500] and "<body>" not in html[:1000]:
            print(f"Requests content too short or looks like SPA, switching to Pyppeteer for {url}")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            html = loop.run_until_complete(_get_html_via_pyppeteer(url))
            loop.close()
    except Exception as e:
        print(f"Requests failed for {url}: {e}, switching to Pyppeteer")
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            html = loop.run_until_complete(_get_html_via_pyppeteer(url))
            loop.close()
        except Exception as e2:
            print(f"Pyppeteer also failed for {url}: {e2}")
            raise e2

    doc = Document(html)
    summary_html = doc.summary()
    print(f"DEBUG: Readability summary length: {len(summary_html)}")
    
    soup = BeautifulSoup(summary_html, "lxml")
    title = doc.title()
    text = soup.get_text("\n", strip=True)
    print(f"DEBUG: Extracted text length (from Readability): {len(text)}")
    
    # Double check: 如果 Readability 提取后没东西，可能是提取失败，回退到原始 HTML 提取
    if len(text) < 50:
         print("DEBUG: Text too short, falling back to raw HTML extraction")
         soup_raw = BeautifulSoup(html, "lxml")
         text = soup_raw.get_text("\n", strip=True)
         print(f"DEBUG: Extracted text length (from Raw HTML): {len(text)}")
 
         text_raw = text
         # 如果原始 HTML 提取出来也很短，或者是 SPA 骨架屏，则触发 Pyppeteer
         # 掘金等网站的骨架屏通常有几百字符的导航栏，所以阈值要适当提高，或者检查特定关键字
         if len(text_raw) < 1000 or ("<div id=\"root\"></div>" in html or "<body><script>" in html.replace(" ", "")):
             print(f"DEBUG: Content still looks like SPA/Skeleton ({len(text_raw)} chars), switching to Pyppeteer")
             try:
                 loop = asyncio.new_event_loop()
                 asyncio.set_event_loop(loop)
                 html_dynamic = loop.run_until_complete(_get_html_via_pyppeteer(url))
                 loop.close()
                 print(f"DEBUG: Pyppeteer returned {len(html_dynamic)} chars")
                 
                 # 对动态渲染后的 HTML 再做一次 Readability + 提取
                 # 注意：对于某些网站，Readability 清洗后可能丢失正文，所以这里如果 Readability 结果太短，优先使用 raw text
                 doc_dyn = Document(html_dynamic)
                 summary_dyn = doc_dyn.summary()
                 text_dyn = BeautifulSoup(summary_dyn, "lxml").get_text("\n", strip=True)
                 print(f"DEBUG: Readability extracted {len(text_dyn)} chars from dynamic HTML")
                 
                 if len(text_dyn) < 100:
                     print("DEBUG: Readability result too short, falling back to raw dynamic HTML")
                     text_dyn = BeautifulSoup(html_dynamic, "lxml").get_text("\n", strip=True)
                 
                 text = text_dyn
                 print(f"DEBUG: Final extracted text length (via Pyppeteer): {len(text)}")
                 
             except Exception as e:
                 print(f"Pyppeteer failed: {e}")
                 text = text_raw # Fallback to whatever we got from requests
         else:
             text = text_raw

    source_id = source_id or (title or url)
    chunks: List[Dict] = []
    _add_chunks(chunks, source_id, "url", text, url=url)
    print(f"DEBUG: Generated {len(chunks)} chunks")
    return chunks


from .notebooks import NotebookManager

def save_chunks(new_chunks: List[Dict], notebook_id: Optional[str] = None) -> Dict[str, int]:
    ensure_data_dir()
    
    if notebook_id:
        chunks_path = NotebookManager.get_notebook_chunks_path(notebook_id)
    else:
        chunks_path = CHUNKS_PATH
        
    print(f"DEBUG: save_chunks called with {len(new_chunks)} chunks for notebook {notebook_id}")
    
    if os.path.exists(chunks_path):
        with open(chunks_path, "r", encoding="utf-8") as f:
            try:
                existing = json.load(f)
            except json.JSONDecodeError:
                existing = []
    else:
        existing = []
    
    before = len(existing)
    existing.extend(new_chunks)
    
    print(f"DEBUG: Writing {len(existing)} chunks to {chunks_path}")
    with open(chunks_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    return {"added": len(new_chunks), "total": len(existing), "before": before}


def load_chunks(notebook_id: Optional[str] = None) -> List[Dict]:
    ensure_data_dir()
    
    if notebook_id:
        chunks_path = NotebookManager.get_notebook_chunks_path(notebook_id)
    else:
        chunks_path = CHUNKS_PATH
        
    if not os.path.exists(chunks_path):
        return []
    with open(chunks_path, "r", encoding="utf-8") as f:
        return json.load(f)
