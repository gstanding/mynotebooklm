import sqlite3
import os
import json
from typing import List, Dict, Optional, Tuple

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DB_PATH = os.path.join(DATA_DIR, "notebooklm.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # Notebooks table
    c.execute('''
        CREATE TABLE IF NOT EXISTS notebooks (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            created_at REAL,
            description TEXT
        )
    ''')
    
    # Sources table
    # id is the source_id (filename/url)
    # PK is composite (notebook_id, id)
    c.execute('''
        CREATE TABLE IF NOT EXISTS sources (
            id TEXT,
            notebook_id TEXT NOT NULL,
            source_type TEXT,
            file_name TEXT,
            created_at REAL,
            enabled INTEGER DEFAULT 1,
            meta_data TEXT,
            PRIMARY KEY (notebook_id, id),
            FOREIGN KEY(notebook_id) REFERENCES notebooks(id) ON DELETE CASCADE
        )
    ''')
    
    # Chunks table
    c.execute('''
        CREATE TABLE IF NOT EXISTS chunks (
            id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL,
            notebook_id TEXT NOT NULL,
            text TEXT,
            location TEXT,
            image_path TEXT,
            created_at REAL,
            meta_data TEXT,
            FOREIGN KEY(notebook_id, source_id) REFERENCES sources(notebook_id, id) ON DELETE CASCADE,
            FOREIGN KEY(notebook_id) REFERENCES notebooks(id) ON DELETE CASCADE
        )
    ''')
    
    conn.commit()
    conn.close()

# --- Notebook Operations ---

def list_notebooks_db() -> List[Dict]:
    conn = get_db_connection()
    notebooks = conn.execute('SELECT * FROM notebooks ORDER BY created_at DESC').fetchall()
    conn.close()
    return [dict(n) for n in notebooks]

def create_notebook_db(notebook_id: str, title: str, created_at: float):
    conn = get_db_connection()
    conn.execute(
        'INSERT INTO notebooks (id, title, created_at) VALUES (?, ?, ?)',
        (notebook_id, title, created_at)
    )
    conn.commit()
    conn.close()

def delete_notebook_db(notebook_id: str):
    conn = get_db_connection()
    conn.execute('PRAGMA foreign_keys = ON')
    conn.execute('DELETE FROM notebooks WHERE id = ?', (notebook_id,))
    conn.commit()
    conn.close()

def get_notebook_db(notebook_id: str) -> Optional[Dict]:
    conn = get_db_connection()
    n = conn.execute('SELECT * FROM notebooks WHERE id = ?', (notebook_id,)).fetchone()
    conn.close()
    return dict(n) if n else None

# --- Source Operations ---

def get_source_db(notebook_id: str, source_id: str) -> Optional[Dict]:
    conn = get_db_connection()
    s = conn.execute('SELECT * FROM sources WHERE notebook_id = ? AND id = ?', (notebook_id, source_id)).fetchone()
    conn.close()
    return dict(s) if s else None

def create_source_db(source_id: str, notebook_id: str, source_type: str, file_name: str, created_at: float, meta_data: Dict = {}):
    conn = get_db_connection()
    # print(f"DEBUG DB: Inserting source {source_id} for notebook {notebook_id}")
    try:
        conn.execute(
            'INSERT OR IGNORE INTO sources (id, notebook_id, source_type, file_name, created_at, meta_data) VALUES (?, ?, ?, ?, ?, ?)',
            (source_id, notebook_id, source_type, file_name, created_at, json.dumps(meta_data))
        )
        conn.commit()
    except Exception as e:
        print(f"ERROR DB: Failed to insert source: {e}")
    finally:
        conn.close()

def list_sources_db(notebook_id: str) -> List[Dict]:
    conn = get_db_connection()
    # Join with chunks count and alias id to source_id
    query = '''
        SELECT s.*, 
               (SELECT COUNT(*) FROM chunks c WHERE c.source_id = s.id AND c.notebook_id = s.notebook_id) as chunk_count
        FROM sources s 
        WHERE s.notebook_id = ?
    '''
    sources = conn.execute(query, (notebook_id,)).fetchall()
    conn.close()
    
    results = []
    for s in sources:
        d = dict(s)
        # Compatibility with frontend
        d['source_id'] = d['id']
        
        # Unpack meta_data
        if d['meta_data']:
            try:
                d.update(json.loads(d['meta_data']))
            except:
                pass
        # Ensure enabled is boolean
        d['enabled'] = bool(d['enabled'])
        results.append(d)
    return results

def update_source_status_db(notebook_id: str, source_id: str, enabled: bool):
    conn = get_db_connection()
    conn.execute('UPDATE sources SET enabled = ? WHERE notebook_id = ? AND id = ?', (1 if enabled else 0, notebook_id, source_id))
    conn.commit()
    conn.close()

def delete_source_db(notebook_id: str, source_id: str):
    conn = get_db_connection()
    conn.execute('PRAGMA foreign_keys = ON')
    conn.execute('DELETE FROM sources WHERE notebook_id = ? AND id = ?', (notebook_id, source_id))
    conn.commit()
    conn.close()

# --- Chunk Operations ---

def create_chunks_batch_db(chunks: List[Dict]):
    conn = get_db_connection()
    
    data_to_insert = []
    for c in chunks:
        meta = {k: v for k, v in c.items() if k not in ['id', 'source_id', 'notebook_id', 'text', 'location', 'image_path', 'created_at']}
        data_to_insert.append((
            c['id'],
            c['source_id'],
            c['notebook_id'],
            c.get('text', ''),
            c.get('location', ''),
            c.get('image_path', ''),
            c.get('created_at', 0),
            json.dumps(meta)
        ))
        
    conn.executemany(
        'INSERT OR REPLACE INTO chunks (id, source_id, notebook_id, text, location, image_path, created_at, meta_data) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        data_to_insert
    )
    conn.commit()
    conn.close()

def load_chunks_db(notebook_id: str) -> List[Dict]:
    """
    Returns chunks in the format expected by the application (flat dicts).
    Only returns chunks from ENABLED sources.
    """
    conn = get_db_connection()
    # Join sources to check enabled status
    # Need to match on both source_id and notebook_id
    query = '''
        SELECT c.*, s.enabled, s.source_type, s.file_name
        FROM chunks c
        JOIN sources s ON c.source_id = s.id AND c.notebook_id = s.notebook_id
        WHERE c.notebook_id = ? AND s.enabled = 1
    '''
    rows = conn.execute(query, (notebook_id,)).fetchall()
    conn.close()
    
    results = []
    for r in rows:
        d = dict(r)
        # Unpack meta_data
        if d['meta_data']:
            try:
                meta = json.loads(d['meta_data'])
                d.update(meta)
            except:
                pass
        del d['meta_data'] # Clean up
        results.append(d)
    return results

def count_chunks_by_source(notebook_id: str, source_id: str) -> int:
    conn = get_db_connection()
    count = conn.execute('SELECT COUNT(*) FROM chunks WHERE notebook_id = ? AND source_id = ?', (notebook_id, source_id)).fetchone()[0]
    conn.close()
    return count
