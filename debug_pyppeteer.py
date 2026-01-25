import asyncio
import os
import shutil
from pyppeteer import launch
from bs4 import BeautifulSoup

async def debug_render(url):
    print(f"DEBUG: Testing Pyppeteer render for {url}")
    
    # 使用项目内的临时目录作为 userDataDir，避免系统目录权限问题
    user_data_dir = os.path.join(os.getcwd(), "pyppeteer_data")
    if os.path.exists(user_data_dir):
        shutil.rmtree(user_data_dir, ignore_errors=True)
    os.makedirs(user_data_dir, exist_ok=True)
    
    print(f"DEBUG: Using userDataDir: {user_data_dir}")
    
    try:
        browser = await launch(
            handleSIGINT=False,
            handleSIGTERM=False,
            handleSIGHUP=False,
            headless=True,
            userDataDir=user_data_dir,  # 关键修复：指定可写目录
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        print("DEBUG: Browser launched successfully")
        
        page = await browser.newPage()
        await page.setUserAgent("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36")
        
        print("DEBUG: Navigating to page...")
        await page.goto(url, {"waitUntil": "networkidle2", "timeout": 60000})
        
        content = await page.content()
        print(f"DEBUG: Rendered content length: {len(content)}")
        
        soup = BeautifulSoup(content, "lxml")
        text = soup.get_text("\n", strip=True)
        print(f"DEBUG: Extracted text length: {len(text)}")
        
        if len(text) > 1000:
            print("SUCCESS: Extracted sufficient content.")
            print(f"Sample:\n{text[:200]}...")
        else:
            print("WARNING: Extracted content is still short.")
            
        await browser.close()
        
    except Exception as e:
        print(f"ERROR: Pyppeteer failed: {e}")
    finally:
        # 清理临时目录
        if os.path.exists(user_data_dir):
            shutil.rmtree(user_data_dir, ignore_errors=True)

if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else "https://juejin.cn/"
    loop = asyncio.get_event_loop()
    loop.run_until_complete(debug_render(url))
