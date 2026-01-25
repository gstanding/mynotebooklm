import os
import json
from typing import List, Dict, Optional
from .ingest import load_chunks, save_chunks
from .notebooks import NotebookManager

class SourceManager:
    @staticmethod
    def list_sources(notebook_id: str) -> List[Dict]:
        """
        聚合 chunks.json 中的 source_id，返回 Source 列表。
        实时计算，不依赖额外存储。
        """
        chunks = load_chunks(notebook_id)
        sources_map = {}
        
        for c in chunks:
            sid = c.get("source_id")
            if not sid:
                continue
            
            if sid not in sources_map:
                sources_map[sid] = {
                    "source_id": sid,
                    "source_type": c.get("source_type", "unknown"),
                    "chunk_count": 0,
                    "enabled": c.get("enabled", True), # 默认为 True
                    "created_at": 0 # TODO: 可以从 chunk id 或其他地方获取，暂时不关键
                }
            
            sources_map[sid]["chunk_count"] += 1
            # 如果发现有 chunk 被禁用了，则认为整个 source 被禁用（通常状态是一致的）
            if c.get("enabled") is False:
                sources_map[sid]["enabled"] = False
                
        return list(sources_map.values())

    @staticmethod
    def delete_source(notebook_id: str, source_id: str) -> bool:
        chunks = load_chunks(notebook_id)
        # 过滤掉该 source_id 的所有 chunks
        new_chunks = [c for c in chunks if c.get("source_id") != source_id]
        
        if len(new_chunks) == len(chunks):
            return False
            
        # 覆写 chunks.json
        # 注意：这里不能直接调 ingest.save_chunks，因为它默认是 append 模式
        # 我们需要一个 overwrite 模式的 save
        chunks_path = NotebookManager.get_notebook_chunks_path(notebook_id)
        with open(chunks_path, "w", encoding="utf-8") as f:
            json.dump(new_chunks, f, ensure_ascii=False, indent=2)
            
        return True

    @staticmethod
    def update_source(notebook_id: str, source_id: str, enabled: Optional[bool] = None) -> bool:
        chunks = load_chunks(notebook_id)
        modified = False
        
        for c in chunks:
            if c.get("source_id") == source_id:
                if enabled is not None:
                    c["enabled"] = enabled
                    modified = True
        
        if modified:
            chunks_path = NotebookManager.get_notebook_chunks_path(notebook_id)
            with open(chunks_path, "w", encoding="utf-8") as f:
                json.dump(chunks, f, ensure_ascii=False, indent=2)
            return True
            
        return False
