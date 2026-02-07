"""Tool selection using semantic search on tool descriptions.

This module provides generic tool selection capabilities that can be used
by any example or agent to determine which tools are needed for a task.
"""

import ast
import logging
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Try to import sentence-transformers for semantic search
try:
    from sentence_transformers import SentenceTransformer

    HAS_SENTENCE_TRANSFORMERS = True
except Exception as e:
    HAS_SENTENCE_TRANSFORMERS = False
    SentenceTransformer = None  # type: ignore
    logger.warning(f"sentence-transformers not available or broken ({e}). Using keyword matching instead.")

# Class-level model cache to avoid reloading the model across instances
_SHARED_MODEL: Optional[Any] = None
_SHARED_MODEL_LOCK = None
try:
    import threading
    _SHARED_MODEL_LOCK = threading.Lock()
except ImportError:
    pass


def extract_tool_description(tool_code: str) -> str:
    """Extract tool description from Python code docstring."""
    try:
        tree = ast.parse(tool_code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Get docstring from function
                docstring = ast.get_docstring(node)
                if docstring:
                    return docstring
                # If no docstring, use function name and parameters as description
                params = [arg.arg for arg in node.args.args]
                return f"{node.name}({', '.join(params)})"
    except Exception as e:
        logger.debug(f"Failed to extract tool description: {e}")
    return ""


class ToolSelector:
    """Generic tool selector that uses semantic search to find relevant tools."""

    def __init__(
        self,
        similarity_threshold: float = 0.3,
        top_k: int = 5,
        use_semantic_search: bool = True,
    ):
        """Initialize tool selector.

        Args:
            similarity_threshold: Minimum similarity score for tool selection
            top_k: Maximum number of tools to return
            use_semantic_search: Whether to use semantic search (requires sentence-transformers)
        """
        self.similarity_threshold = similarity_threshold
        self.top_k = top_k
        self.use_semantic_search = use_semantic_search and HAS_SENTENCE_TRANSFORMERS
        self._model: Optional[Any] = None

    def _get_model(self, use_gpu: bool = True) -> Optional[Any]:
        """Lazy load the sentence transformer model (uses shared cache).
        
        Args:
            use_gpu: Whether to use GPU if available (from config)
        """
        global _SHARED_MODEL
        
        if not self.use_semantic_search:
            return None

        # Use instance model if available
        if self._model is not None:
            return self._model
        
        # Try to use shared model cache (thread-safe)
        if _SHARED_MODEL is not None:
            self._model = _SHARED_MODEL
            return self._model
        
        # Load model (with lock if available)
        if _SHARED_MODEL_LOCK:
            with _SHARED_MODEL_LOCK:
                # Double-check after acquiring lock
                if _SHARED_MODEL is not None:
                    self._model = _SHARED_MODEL
                    return self._model
                
                try:
                    # Check for GPU support (optimization)
                    device = "cpu"
                    if use_gpu:
                        try:
                            import torch
                            if torch.cuda.is_available():
                                device = "cuda"
                                logger.info("GPU available, using CUDA for embeddings")
                            else:
                                logger.debug("GPU not available, using CPU")
                        except Exception as e:
                            logger.debug(f"PyTorch not available or broken ({e}), using CPU")
                    
                    logger.info(f"Loading sentence-transformers model on {device}...")
                    # Use a lightweight, fast model
                    _SHARED_MODEL = SentenceTransformer("all-MiniLM-L6-v2", device=device)
                    self._model = _SHARED_MODEL
                    logger.info(f"Model loaded on {device} and cached for future use")
                except Exception as e:
                    logger.warning(f"Failed to load sentence-transformers model: {e}")
                    self.use_semantic_search = False
                    return None
        else:
            # No threading, just load directly
            try:
                device = "cpu"
                if use_gpu:
                    try:
                        import torch
                        device = "cuda" if torch.cuda.is_available() else "cpu"
                    except Exception as e:
                        logger.debug(f"PyTorch broken ({e}), using CPU")
                
                logger.info(f"Loading sentence-transformers model on {device}...")
                self._model = SentenceTransformer("all-MiniLM-L6-v2", device=device)
                _SHARED_MODEL = self._model
            except Exception as e:
                logger.warning(f"Failed to load sentence-transformers model: {e}")
                self.use_semantic_search = False
                return None

        return self._model

    def get_tool_descriptions(
        self,
        fs_helper: Any,  # FilesystemHelper
        discovered_servers: Dict[str, List[str]],
    ) -> Dict[Tuple[str, str], str]:
        """Extract descriptions for all discovered tools.

        Args:
            fs_helper: FilesystemHelper instance
            discovered_servers: Dict mapping server names to lists of tool names

        Returns:
            Dict mapping (server_name, tool_name) tuples to descriptions
        """
        tool_descriptions = {}
        for server_name, tools in discovered_servers.items():
            for tool_name in tools:
                tool_code = fs_helper.read_tool_file(server_name, tool_name)
                if tool_code:
                    description = extract_tool_description(tool_code)
                    # Include server and tool name in description for better matching
                    full_description = f"{server_name} {tool_name}: {description}"
                    tool_descriptions[(server_name, tool_name)] = full_description
        return tool_descriptions

    def select_tools(
        self,
        task_description: str,
        tool_descriptions: Dict[Tuple[str, str], str],
        use_gpu: bool = True,
    ) -> Dict[str, List[str]]:
        """Select relevant tools for a task using semantic search.

        Args:
            task_description: Description of the task to accomplish
            tool_descriptions: Dict mapping (server_name, tool_name) to descriptions
            use_gpu: Whether to use GPU if available (from config)

        Returns:
            Dict mapping server names to lists of selected tool names
        """
        if self.use_semantic_search:
            return self._semantic_search_tools(task_description, tool_descriptions, use_gpu=use_gpu)
        else:
            return self._keyword_match_tools(task_description, tool_descriptions)

    def _semantic_search_tools(
        self,
        task_description: str,
        tool_descriptions: Dict[Tuple[str, str], str],
        use_gpu: bool = True,
    ) -> Dict[str, List[str]]:
        """Use semantic search to find relevant tools.
        
        Args:
            task_description: Task description
            tool_descriptions: Tool descriptions  
            use_gpu: Whether to use GPU if available (from config)
        """
        model = self._get_model(use_gpu=use_gpu)
        if model is None:
            logger.warning("Falling back to keyword matching")
            return self._keyword_match_tools(task_description, tool_descriptions)

        try:
            # Determine device for PyTorch operations
            import torch
            device = "cuda" if (use_gpu and torch.cuda.is_available()) else "cpu"
            
            # Create embeddings for task (as tensor for efficient computation)
            task_embedding = model.encode(
                task_description, convert_to_tensor=True, show_progress_bar=False
            )
            task_embedding = task_embedding.to(device)

            # Create embeddings for all tools (as tensor for efficient computation)
            tool_texts = list(tool_descriptions.values())
            tool_keys = list(tool_descriptions.keys())

            logger.debug(f"Encoding {len(tool_texts)} tool descriptions...")
            tool_embeddings = model.encode(
                tool_texts, convert_to_tensor=True, show_progress_bar=False
            )
            tool_embeddings = tool_embeddings.to(device)

            # Calculate cosine similarities using PyTorch
            # Normalize embeddings for cosine similarity
            task_embedding_norm = torch.nn.functional.normalize(task_embedding, p=2, dim=0)
            tool_embeddings_norm = torch.nn.functional.normalize(tool_embeddings, p=2, dim=1)
            
            # Compute cosine similarity: dot product of normalized vectors
            # Shape: (num_tools,) - one similarity score per tool
            similarities = torch.mm(
                tool_embeddings_norm, 
                task_embedding_norm.unsqueeze(1)
            ).squeeze(1)
            
            # Get top-k tools above threshold
            # Get top-k indices sorted by similarity (descending)
            top_k = min(self.top_k, len(similarities))
            top_similarities, top_indices = torch.topk(similarities, k=top_k, largest=True)
            
            # Convert to CPU and Python lists for threshold filtering
            top_similarities = top_similarities.cpu().tolist()
            top_indices = top_indices.cpu().tolist()

            selected_tools = {}

            for idx, similarity in zip(top_indices, top_similarities):
                if similarity >= self.similarity_threshold:
                    server_name, tool_name = tool_keys[idx]
                    if server_name not in selected_tools:
                        selected_tools[server_name] = []
                    selected_tools[server_name].append(tool_name)
                    logger.debug(
                        f"Selected {server_name}.{tool_name} (similarity: {similarity:.3f})"
                    )

            return selected_tools

        except Exception as e:
            logger.warning(f"Semantic search failed ({e}), falling back to keyword matching")
            return self._keyword_match_tools(task_description, tool_descriptions)

    def _keyword_match_tools(
        self,
        task_description: str,
        tool_descriptions: Dict[Tuple[str, str], str],
    ) -> Dict[str, List[str]]:
        """Simple keyword-based tool matching (fallback)."""
        task_lower = task_description.lower()
        selected_tools = {}

        # Simple keyword matching
        keywords = {
            "calculator": [
                "calculate",
                "add",
                "multiply",
                "math",
                "compute",
                "sum",
                "subtract",
                "divide",
            ],
            "weather": ["weather", "temperature", "forecast", "climate", "rain", "sunny"],
            "filesystem": ["file", "read", "write", "directory", "folder", "path"],
            "database": ["database", "query", "sql", "table", "data", "insert", "select"],
        }

        for (server_name, tool_name), description in tool_descriptions.items():
            desc_lower = description.lower()
            # Check if task keywords match tool description
            server_keywords = keywords.get(server_name, [])
            if any(keyword in task_lower and keyword in desc_lower for keyword in server_keywords):
                if server_name not in selected_tools:
                    selected_tools[server_name] = []
                selected_tools[server_name].append(tool_name)
                logger.debug(f"Selected {server_name}.{tool_name} (keyword match)")

        return selected_tools
