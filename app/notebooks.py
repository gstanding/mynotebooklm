import os
import json
import time
import shutil
from typing import List, Dict, Optional
import uuid

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
NOTEBOOKS_DIR = os.path.join(DATA_DIR, "notebooks")
NOTEBOOKS_META_PATH = os.path.join(DATA_DIR, "notebooks.json")

def ensure_notebooks_dir():
    os.makedirs(NOTEBOOKS_DIR, exist_ok=True)
    if not os.path.exists(NOTEBOOKS_META_PATH):
        with open(NOTEBOOKS_META_PATH, "w", encoding="utf-8") as f:
            json.dump([], f)

class NotebookManager:
    @staticmethod
    def list_notebooks() -> List[Dict]:
        ensure_notebooks_dir()
        with open(NOTEBOOKS_META_PATH, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []

    @staticmethod
    def create_notebook(title: str) -> Dict:
        ensure_notebooks_dir()
        notebooks = NotebookManager.list_notebooks()
        
        new_id = str(uuid.uuid4())
        new_notebook = {
            "id": new_id,
            "title": title,
            "created_at": time.time()
        }
        
        # 创建该 Notebook 的专属数据目录
        notebook_path = os.path.join(NOTEBOOKS_DIR, new_id)
        os.makedirs(notebook_path, exist_ok=True)
        # 初始化空的 chunks.json
        with open(os.path.join(notebook_path, "chunks.json"), "w", encoding="utf-8") as f:
            json.dump([], f)
            
        notebooks.append(new_notebook)
        with open(NOTEBOOKS_META_PATH, "w", encoding="utf-8") as f:
            json.dump(notebooks, f, indent=2, ensure_ascii=False)
            
        return new_notebook

    @staticmethod
    def delete_notebook(notebook_id: str) -> bool:
        ensure_notebooks_dir()
        notebooks = NotebookManager.list_notebooks()
        
        # 过滤掉要删除的
        new_list = [n for n in notebooks if n["id"] != notebook_id]
        if len(new_list) == len(notebooks):
            return False # ID 不存在
            
        # 更新元数据
        with open(NOTEBOOKS_META_PATH, "w", encoding="utf-8") as f:
            json.dump(new_list, f, indent=2, ensure_ascii=False)
            
        # 删除物理目录
        notebook_path = os.path.join(NOTEBOOKS_DIR, notebook_id)
        if os.path.exists(notebook_path):
            shutil.rmtree(notebook_path, ignore_errors=True)
            
        return True

    @staticmethod
    def get_notebook_chunks_path(notebook_id: str) -> str:
        return os.path.join(NOTEBOOKS_DIR, notebook_id, "chunks.json")
