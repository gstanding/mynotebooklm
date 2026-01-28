import os
import json
import sys
import time

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import init_db, create_notebook_db, create_source_db, create_chunks_batch_db
# from app.notebooks import NotebookManager # Don't use this as it now points to DB

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
NOTEBOOKS_META_PATH = os.path.join(DATA_DIR, "notebooks.json")
NOTEBOOKS_DIR = os.path.join(DATA_DIR, "notebooks")

def migrate():
    print("Starting migration to SQLite...")
    
    # 1. Init DB
    init_db()
    print("Database initialized.")
    
    # 2. Read notebooks from JSON
    if not os.path.exists(NOTEBOOKS_META_PATH):
        print("No notebooks.json found. Nothing to migrate.")
        return
        
    with open(NOTEBOOKS_META_PATH, "r", encoding="utf-8") as f:
        try:
            notebooks = json.load(f)
        except:
            notebooks = []
            
    print(f"Found {len(notebooks)} notebooks in JSON.")
    
    for nb in notebooks:
        print(f"Migrating notebook: {nb['title']} ({nb['id']})")
        
        # Insert Notebook
        # Check if exists first to avoid duplicate if re-running
        try:
            create_notebook_db(nb['id'], nb['title'], nb.get('created_at', time.time()))
        except Exception as e:
            print(f"  Note: Notebook might already exist: {e}")
        
        # Read chunks
        chunks_path = os.path.join(NOTEBOOKS_DIR, nb['id'], "chunks.json")
        if not os.path.exists(chunks_path):
            print(f"  No chunks file found for {nb['title']}")
            continue
            
        with open(chunks_path, 'r', encoding='utf-8') as f:
            try:
                chunks = json.load(f)
            except:
                chunks = []
                
        print(f"  Found {len(chunks)} chunks.")
        
        # Identify Sources
        # Map source_id -> source_info
        sources = {}
        chunks_to_insert = []
        
        for chunk in chunks:
            sid = chunk.get('source_id')
            if not sid:
                continue
                
            if sid not in sources:
                # Infer source info from the first chunk we see
                sources[sid] = {
                    'id': sid,
                    'notebook_id': nb['id'],
                    'source_type': chunk.get('source_type', 'unknown'),
                    'file_name': sid, # Use source_id as filename for now
                    'created_at': time.time(),
                    'meta_data': {
                        'url': chunk.get('url'),
                        'path': chunk.get('path')
                    }
                }
            
            # Prepare chunk for DB
            # Ensure notebook_id is present
            chunk['notebook_id'] = nb['id']
            # Ensure created_at
            if 'created_at' not in chunk:
                chunk['created_at'] = time.time()
                
            chunks_to_insert.append(chunk)
            
        # Insert Sources
        print(f"  Creating {len(sources)} sources...")
        for s in sources.values():
            create_source_db(
                s['id'], 
                s['notebook_id'], 
                s['source_type'], 
                s['file_name'], 
                s['created_at'], 
                s['meta_data']
            )
            
        # Insert Chunks
        print(f"  Inserting {len(chunks_to_insert)} chunks...")
        if chunks_to_insert:
            create_chunks_batch_db(chunks_to_insert)
            
    print("Migration completed successfully.")

if __name__ == "__main__":
    migrate()
