import json
import os
import time
from typing import Dict, List, Optional
import requests
from bs4 import BeautifulSoup
from readability import Document
import fitz  # PyMuPDF
from .utils import clean_text, chunk_text
from .ocr import ocr_image
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
        doc = fitz.open(file_path)
        print(f"DEBUG: Processing PDF {file_path} with {len(doc)} pages")
        
        for i, page in enumerate(doc):
            try:
                # 1. 尝试直接提取文本
                text = page.get_text() or ""
                
                # 2. OCR 增强逻辑：如果页面包含图片，尝试对图片进行 OCR
                # PyMuPDF 的 get_images() 返回页面内的图片列表
                images = page.get_images(full=True)
                if images:
                    print(f"DEBUG: Page {i+1} has {len(images)} images, attempting OCR...")
                    ocr_texts = []
                    for img_index, img in enumerate(images):
                        try:
                            xref = img[0]
                            base_image = doc.extract_image(xref)
                            image_bytes = base_image["image"]
                            
                            # 简单的去重逻辑：如果这一页已经提取了很多文本（>500字），
                            # 且图片较小（可能是图标），则跳过 OCR 以节省时间
                            # 这里暂不实现复杂的重叠检测，而是简单地将 OCR 结果追加到文本末尾
                            ocr_res = ocr_image(image_bytes)
                            if ocr_res:
                                ocr_texts.append(ocr_res)
                        except Exception as e:
                            print(f"WARNING: Failed to extract/OCR image {img_index} on page {i+1}: {e}")
                    
                    if ocr_texts:
                        combined_ocr = "\n".join(ocr_texts)
                        print(f"DEBUG: OCR extracted {len(combined_ocr)} chars from images on page {i+1}")
                        # 将 OCR 结果追加到页面文本末尾
                        text += "\n" + combined_ocr
                
                # 3. 如果整页依然没文本（既没文字层也没提取出 OCR），尝试整页渲染 OCR
                # 这是最后的保底，防止漏掉那些“绘制”出来的文字（非 Image 对象）
                if len(text.strip()) < 50:
                    print(f"DEBUG: Page {i+1} still has little text ({len(text.strip())} chars), attempting full-page OCR...")
                    try:
                        # 渲染页面为图片 (dpi=300 提升清晰度)
                        pix = page.get_pixmap(dpi=300)
                        img_bytes = pix.tobytes("png")
                        ocr_text = ocr_image(img_bytes)
                        if ocr_text:
                            print(f"DEBUG: Full-page OCR extracted {len(ocr_text)} chars from page {i+1}")
                            text += "\n" + ocr_text
                    except Exception as e:
                        print(f"ERROR: Full-page OCR failed for page {i+1}: {e}")

                if text.strip():
                    _add_chunks(chunks, source_id, "pdf", text, location=f"page {i+1}", path=file_path)
            except Exception as e:
                print(f"Error reading page {i} of {file_path}: {e}")
                continue
                
        doc.close()
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
            # If both fail, we might want to return empty list instead of crashing
            # or raise a more user-friendly error.
            # For now, let's catch it and return empty list so other sources can proceed.
            return []

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
from .db import (
    load_chunks_db, 
    create_chunks_batch_db, 
    create_source_db,
    count_chunks_by_source,
    get_source_db
)

def load_chunks(notebook_id: Optional[str] = None) -> List[Dict]:
    return load_chunks_db(notebook_id)

def save_chunks(new_chunks: List[Dict], notebook_id: Optional[str] = None) -> Dict[str, int]:
    ensure_data_dir()
    
    if not notebook_id:
        # Fallback for legacy global mode or error
        print("WARNING: save_chunks called without notebook_id, skipping persistence.")
        return {"added": 0, "total": 0, "before": 0}
        
    print(f"DEBUG: save_chunks called with {len(new_chunks)} chunks for notebook {notebook_id}")
    
    # 1. Identify and Create Sources
    # Map source_id -> source info from the first chunk we see for that source
    sources_to_create = {}
    
    for chunk in new_chunks:
        # Inject notebook_id
        chunk['notebook_id'] = notebook_id
        # Ensure created_at
        if 'created_at' not in chunk:
            chunk['created_at'] = time.time()
            
        sid = chunk.get('source_id')
        if not sid:
            continue
            
        if sid not in sources_to_create:
            # Check if source already exists in DB to avoid overhead? 
            # create_source_db uses INSERT OR IGNORE, so it's safe.
            sources_to_create[sid] = {
                'id': sid,
                'notebook_id': notebook_id,
                'source_type': chunk.get('source_type', 'unknown'),
                'file_name': sid, # Use source_id as filename default
                'created_at': chunk.get('created_at'),
                'meta_data': {
                    'url': chunk.get('url'),
                    'path': chunk.get('path')
                }
            }
            
    # Batch create sources
    for s in sources_to_create.values():
        create_source_db(
            s['id'], 
            s['notebook_id'], 
            s['source_type'], 
            s['file_name'], 
            s['created_at'], 
            s['meta_data']
        )
        
    # 2. Save Chunks
    # We need to know how many chunks were there before.
    # This is expensive to count globally, maybe just return added count?
    # The API returns {"added": ..., "total": ..., "before": ...}
    # We can get total count for this notebook from DB.
    # For now, let's just approximate or query.
    
    # Actually, let's just insert.
    create_chunks_batch_db(new_chunks)
    
    return {"added": len(new_chunks), "total": -1, "before": -1}
