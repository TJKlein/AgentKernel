"""Tool description cache for fast tool discovery."""

import json
import hashlib
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class ToolCache:
    """Persistent cache for tool descriptions.
    
    This optimization speeds up tool discovery by caching parsed
    tool descriptions and only re-parsing when files change.
    
    Can be disabled via config: optimizations.tool_cache = False
    """
    
    def __init__(self, cache_file: str = ".tool_cache.json"):
        """Initialize tool cache.
        
        Args:
            cache_file: Path to cache file
        """
        self.cache_file = Path(cache_file)
        self.cache: Dict = self._load_cache()
        self._dirty = False
        
        logger.debug(f"Tool cache initialized (file={cache_file}, tools={len(self.cache.get('tools', {}))})")
    
    def _load_cache(self) -> Dict:
        """Load cache from disk."""
        if self.cache_file.exists():
            try:
                cache = json.loads(self.cache_file.read_text(encoding="utf-8"))
                logger.info(f"Loaded tool cache with {len(cache.get('tools', {}))} entries")
                return cache
            except Exception as e:
                logger.warning(f"Failed to load tool cache: {e}")
        
        return {"version": "1.0", "tools": {}}
    
    def _save_cache(self):
        """Save cache to disk."""
        if not self._dirty:
            return
        
        try:
            self.cache_file.write_text(
                json.dumps(self.cache, indent=2), 
                encoding="utf-8"
            )
            self._dirty = False
            logger.debug(f"Saved tool cache with {len(self.cache['tools'])} entries")
        except Exception as e:
            logger.warning(f"Failed to save tool cache: {e}")
    
    def get_tool_description(
        self, 
        server: str, 
        tool: str, 
        source_file: Path
    ) -> Optional[str]:
        """Get tool description from cache.
        
        Args:
            server: Server name
            tool: Tool name  
            source_file: Source file path
            
        Returns:
            Cached description or None if not cached/stale
        """
        key = f"{server}.{tool}"
        
        if key not in self.cache["tools"]:
            return None
        
        cached = self.cache["tools"][key]
        
        # Check if file was modified
        if not source_file.exists():
            return None
        
        current_hash = self._file_hash(source_file)
        if cached.get("hash") != current_hash:
            logger.debug(f"Cache miss for {key} (file modified)")
            return None
        
        logger.debug(f"Cache hit for {key}")
        return cached.get("description")
    
    def set_tool_description(
        self,
        server: str,
        tool: str,
        description: str,
        source_file: Path
    ):
        """Cache tool description.
        
        Args:
            server: Server name
            tool: Tool name
            description: Tool description
            source_file: Source file path
        """
        key = f"{server}.{tool}"
        self.cache["tools"][key] = {
            "description": description,
            "hash": self._file_hash(source_file),
            "path": str(source_file),
            "server": server,
            "tool": tool
        }
        self._dirty = True
        logger.debug(f"Cached description for {key}")
    
    def _file_hash(self, path: Path) -> str:
        """Compute MD5 hash of file."""
        try:
            return hashlib.md5(path.read_bytes()).hexdigest()
        except Exception:
            return ""
    
    def save(self):
        """Force save cache to disk."""
        self._save_cache()
    
    def clear(self):
        """Clear all cache entries."""
        self.cache["tools"] = {}
        self._dirty = True
        self._save_cache()
        logger.info("Tool cache cleared")
    
    def get_stats(self) -> Dict:
        """Get cache statistics."""
        return {
            "total_entries": len(self.cache.get("tools", {})),
            "cache_file": str(self.cache_file),
            "cache_size_bytes": self.cache_file.stat().st_size if self.cache_file.exists() else 0
        }
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - save cache."""
        self.save()


# Global cache instance (singleton pattern)
_global_cache: Optional[ToolCache] = None


def get_tool_cache(cache_file: str = ".tool_cache.json") -> ToolCache:
    """Get or create the global tool cache.
    
    Args:
        cache_file: Path to cache file
        
    Returns:
        Global tool cache instance
    """
    global _global_cache
    
    if _global_cache is None:
        _global_cache = ToolCache(cache_file)
    
    return _global_cache

