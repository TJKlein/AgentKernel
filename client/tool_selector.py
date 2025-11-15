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
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False
    SentenceTransformer = None  # type: ignore
    logger.warning("sentence-transformers not available. Using keyword matching instead.")


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

    def _get_model(self) -> Optional[Any]:
        """Lazy load the sentence transformer model."""
        if not self.use_semantic_search:
            return None

        if self._model is None:
            try:
                logger.info("Loading sentence-transformers model for semantic search...")
                # Use a lightweight, fast model
                self._model = SentenceTransformer("all-MiniLM-L6-v2")
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
    ) -> Dict[str, List[str]]:
        """Select relevant tools for a task using semantic search.

        Args:
            task_description: Description of the task to accomplish
            tool_descriptions: Dict mapping (server_name, tool_name) to descriptions

        Returns:
            Dict mapping server names to lists of selected tool names
        """
        if self.use_semantic_search:
            return self._semantic_search_tools(task_description, tool_descriptions)
        else:
            return self._keyword_match_tools(task_description, tool_descriptions)

    def _semantic_search_tools(
        self,
        task_description: str,
        tool_descriptions: Dict[Tuple[str, str], str],
    ) -> Dict[str, List[str]]:
        """Use semantic search to find relevant tools."""
        model = self._get_model()
        if model is None:
            logger.warning("Falling back to keyword matching")
            return self._keyword_match_tools(task_description, tool_descriptions)

        try:
            # Create embeddings for task
            task_embedding = model.encode(
                task_description, convert_to_tensor=False, show_progress_bar=False
            )

            # Create embeddings for all tools
            tool_texts = list(tool_descriptions.values())
            tool_keys = list(tool_descriptions.keys())

            logger.debug(f"Encoding {len(tool_texts)} tool descriptions...")
            tool_embeddings = model.encode(
                tool_texts, convert_to_tensor=False, show_progress_bar=False
            )

            # Calculate cosine similarities
            from numpy import dot
            from numpy.linalg import norm

            similarities = []
            for tool_emb in tool_embeddings:
                # Cosine similarity
                similarity = dot(task_embedding, tool_emb) / (norm(task_embedding) * norm(tool_emb))
                similarities.append(float(similarity))

            # Get top-k tools above threshold
            indexed_sims = list(enumerate(similarities))
            indexed_sims.sort(key=lambda x: x[1], reverse=True)
            top_indices = [idx for idx, _ in indexed_sims[: self.top_k]]

            selected_tools = {}

            for idx in top_indices:
                similarity = similarities[idx]
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
