import sys
import os
import requests
from readability import Document
from bs4 import BeautifulSoup

def debug_url_ingest(url: str):
    print(f"Fetching {url}...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        print(f"Status Code: {resp.status_code}")
        print(f"Content Length: {len(resp.text)} chars")
        
        # 保存原始HTML以便排查
        with open("debug_raw.html", "w", encoding="utf-8") as f:
            f.write(resp.text)
        print("Saved raw HTML to debug_raw.html")

        # Readability 提取
        doc = Document(resp.text)
        summary_html = doc.summary()
        with open("debug_readability.html", "w", encoding="utf-8") as f:
            f.write(summary_html)
        print("Saved readability summary to debug_readability.html")

        # BeautifulSoup 提取文本
        soup = BeautifulSoup(summary_html, "lxml")
        title = doc.title()
        print(f"Title: {title}")
        
        # 检查目前的提取策略
        # extracted_p = [t.get_text(" ", strip=True) for t in soup.find_all(["p", "li"])]
        # full_text_p = "\n".join(extracted_p)
        # print(f"Extracted Text (P/LI only): {len(full_text_p)} chars")
        
        # 对比全量文本提取
        full_text_all = soup.get_text("\n", strip=True)
        print(f"Extracted Text (All Tags): {len(full_text_all)} chars")
        
        if len(full_text_all) < 100:
            print("\nWARNING: Extracted text is very short. Possible reasons:")
            print("1. Page content is loaded via JavaScript (SPA).")
            print("2. Readability failed to identify main content.")
            print("3. Page is blocking the request (check debug_raw.html).")
        else:
            print("\nSUCCESS: Extracted sufficient text content.")
            print(f"Sample:\n{full_text_all[:200]}...")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_ingest.py <url>")
    else:
        debug_url_ingest(sys.argv[1])
