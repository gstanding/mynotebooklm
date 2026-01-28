import os
import shutil
import time
import uuid
from typing import Dict, List
from .db import (
    list_notebooks_db, 
    create_notebook_db, 
    delete_notebook_db, 
    get_notebook_db
)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
NOTEBOOKS_DIR = os.path.join(DATA_DIR, "notebooks")

class NotebookManager:
    @staticmethod
    def list_notebooks() -> List[Dict]:
        return list_notebooks_db()

    @staticmethod
    def create_notebook(title: str) -> Dict:
        new_id = str(uuid.uuid4())
        created_at = time.time()
        
        # Write to DB
        create_notebook_db(new_id, title, created_at)
        
        # Create directory (optional now, but kept for compatibility/temp files)
        notebook_path = os.path.join(NOTEBOOKS_DIR, new_id)
        os.makedirs(notebook_path, exist_ok=True)
            
        return {
            "id": new_id,
            "title": title,
            "created_at": created_at
        }

    @staticmethod
    def delete_notebook(notebook_id: str) -> bool:
        # Check existence
        if not get_notebook_db(notebook_id):
            return False
            
        # Delete from DB
        delete_notebook_db(notebook_id)
            
        # Delete physical directory
        notebook_path = os.path.join(NOTEBOOKS_DIR, notebook_id)
        if os.path.exists(notebook_path):
            shutil.rmtree(notebook_path, ignore_errors=True)
            
        return True

    @staticmethod
    def get_notebook_chunks_path(notebook_id: str) -> str:
        # DEPRECATED: Should rely on DB now. 
        # But kept if some external code calls it, though it points to a file that might be stale.
        return os.path.join(NOTEBOOKS_DIR, notebook_id, "chunks.json")
