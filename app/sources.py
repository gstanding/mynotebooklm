import os
import json
from typing import List, Dict, Optional
from .db import (
    list_sources_db,
    update_source_status_db,
    delete_source_db
)

class SourceManager:
    @staticmethod
    def list_sources(notebook_id: str) -> List[Dict]:
        """
        List sources from DB.
        """
        return list_sources_db(notebook_id)

    @staticmethod
    def delete_source(notebook_id: str, source_id: str) -> bool:
        # Note: notebook_id is not strictly needed for delete by ID, but good for validation?
        # For now, just delete by source_id.
        delete_source_db(notebook_id, source_id)
        return True

    @staticmethod
    def update_source(notebook_id: str, source_id: str, enabled: Optional[bool] = None) -> bool:
        if enabled is not None:
            update_source_status_db(notebook_id, source_id, enabled)
            return True
        return False
