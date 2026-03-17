"""Skill management for MCPRuntime.

This module allows agents to save, discover, and reuse code patterns as "skills".
Skills are saved as Python modules in the workspace/skills/ directory with
metadata tracked in SKILLS.md for discovery.

Based on Anthropic's "Skills" pattern from:
https://www.anthropic.com/engineering/code-execution-with-mcp
"""

import json
import logging
import os
import re
import ast
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Pattern abstraction prompt for runtime-evolved skills (pattern-aware retrieval)
ABSTRACTION_PROMPT = """You just solved a programming task. Extract the reusable meta-pattern.

Code:
{successful_code}

Task:
{task_description}

Return ONLY valid JSON: no markdown fences, no code blocks, no extra text. Example:
{{"pattern_name": "x", "pattern_description": "y", "key_operations": [], "transfer_conditions": "z"}}

pattern_name: short identifier (e.g. sliding_window, frequency_counting, temporal_aggregation).
pattern_description: 2-3 sentences on the strategy.
key_operations: list of core operations used.
transfer_conditions: when this pattern applies to new tasks.
"""


class SkillManager:
    """Manages reusable code skills for agents.
    
    Skills are Python functions/modules that agents have created and can
    reuse across sessions. Each skill includes:
    - Python code (saved as .py file)
    - Description (saved in SKILLS.md and skill_index.json)
    - Metadata (creation date, usage count, etc.)
    """
    
    def __init__(self, workspace_dir: str = "./workspace"):
        """Initialize skill manager.
        
        Args:
            workspace_dir: Path to workspace directory
        """
        self.workspace_dir = Path(workspace_dir)
        self.skills_dir = self.workspace_dir / "skills"
        self.skills_file = self.skills_dir / "SKILLS.md"
        self.index_file = self.skills_dir / "skill_index.json"
        self.pattern_metadata_file = self.skills_dir / "pattern_metadata.json"
        self._embed_fn: Optional[Any] = None  # callable(text: str) -> List[float], set by runner for pattern retrieval
        
        # Create skills directory if it doesn't exist
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        
        # Create __init__.py to make it a package
        init_file = self.skills_dir / "__init__.py"
        if not init_file.exists():
            init_file.write_text('"""Agent skills package."""\n')
        
        # Create SKILLS.md if it doesn't exist
        if not self.skills_file.exists():
            self._initialize_skills_file()

        # Create skill_index.json if it doesn't exist
        if not self.index_file.exists():
            self._write_skill_index([])
    
    def _initialize_skills_file(self) -> None:
        """Create initial SKILLS.md file."""
        content = """# Agent Skills

This directory contains reusable code patterns (skills) that the agent has created.
Each skill is a Python module that can be imported and used in future tasks.

## Available Skills

<!--SKILLS_START-->
<!--SKILLS_END-->

## Usage

To use a skill in your code:

```python
from skills.skill_name import run
result = run(args)
```

## Skill Format

Each skill should:
1. Have a clear, descriptive name
2. Be self-contained (minimal external dependencies)
3. Expose a `run(*args, **kwargs)` entry-point function
4. Return results rather than printing them
"""
        self.skills_file.write_text(content)
    
    def save_skill(
        self,
        name: str,
        code: str,
        description: str,
        tags: Optional[List[str]] = None,
        source_task: Optional[str] = None,
    ) -> Dict[str, str]:
        """Save a new skill.
        
        Args:
            name: Skill name (must be valid Python identifier)
            code: Python code for the skill
            description: Human-readable description
            tags: Optional list of tags for categorization
            source_task: Optional task ID that created this skill (e.g. for benchmarks)
            
        Returns:
            Dictionary with status and file path
            
        Raises:
            ValueError: If name is invalid or skill already exists
        """
        # Validate name
        if not self._is_valid_skill_name(name):
            raise ValueError(
                f"Invalid skill name '{name}'. Must be a valid Python identifier "
                "(letters, numbers, underscores, cannot start with number)"
            )
        
        skill_file = self.skills_dir / f"{name}.py"
        
        # Check if skill already exists
        if skill_file.exists():
            raise ValueError(
                f"Skill '{name}' already exists. Use update_skill() to replace it."
            )
        
        return self._write_skill_files(name, code, description, tags, source_task=source_task)

    def update_skill(
        self,
        name: str,
        code: str,
        description: str,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """Update an existing skill or create it if it doesn't exist.
        
        Args:
            name: Skill name (must be valid Python identifier)
            code: Python code for the skill
            description: Human-readable description
            tags: Optional list of tags for categorization
            
        Returns:
            Dictionary with status and file path
        """
        if not self._is_valid_skill_name(name):
            raise ValueError(
                f"Invalid skill name '{name}'. Must be a valid Python identifier"
            )

        skill_file = self.skills_dir / f"{name}.py"
        
        if skill_file.exists():
            # If we are updating, first remove from the markdown registry to avoid duplicates
            self._remove_skill_from_registry(name)

        return self._write_skill_files(name, code, description, tags)

    def _write_skill_files(
        self,
        name: str,
        code: str,
        description: str,
        tags: Optional[List[str]],
        source_task: Optional[str] = None,
    ) -> Dict[str, str]:
        """Internal helper to write the code file and update the registries."""
        skill_file = self.skills_dir / f"{name}.py"
        
        # Add header comment to code if it doesn't have one
        if not code.strip().startswith('"""'):
            source_line = f"source_task: {source_task}\n" if source_task else ""
            header = f'''"""
skill_name: {name}
description: {description}
Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Tags: {', '.join(tags or [])}
{source_line}"""

'''
            full_code = header + code
        else:
            full_code = code
        
        # Save skill file
        skill_file.write_text(full_code)
        
        # Update SKILLS.md
        self._add_skill_to_registry(name, description, tags or [])
        
        # Update skill_index.json
        self._update_skill_index()
        
        logger.info(f"Saved skill '{name}' to {skill_file}")
        
        return {
            "status": "success",
            "name": name,
            "path": str(skill_file),
            "message": f"Skill '{name}' saved successfully"
        }
    
    def get_skill(self, name: str) -> Dict[str, str]:
        """Get skill code and metadata.
        
        Args:
            name: Skill name
            
        Returns:
            Dictionary with skill code and metadata
            
        Raises:
            ValueError: If skill doesn't exist
        """
        skill_file = self.skills_dir / f"{name}.py"
        
        if not skill_file.exists():
            raise ValueError(f"Skill '{name}' not found")
        
        code = skill_file.read_text()
        
        # Extract metadata from docstring
        metadata = self._extract_metadata(code)
        
        return {
            "name": name,
            "code": code,
            "path": str(skill_file),
            **metadata
        }
    
    def list_skills(self) -> List[Dict[str, str]]:
        """List all available skills.
        
        Returns:
            List of dictionaries with skill information
        """
        skills = []
        
        # Find all .py files in skills directory (except __init__.py)
        for skill_file in self.skills_dir.glob("*.py"):
            if skill_file.name == "__init__.py":
                continue
            
            name = skill_file.stem
            code = skill_file.read_text()
            metadata = self._extract_metadata(code)
            
            skill_entry = {
                "name": name,
                "description": metadata.get("description", "No description"),
                "tags": metadata.get("tags", ""),
                "created": metadata.get("created", "Unknown"),
                "path": str(skill_file),
            }
            if metadata.get("source_task"):
                skill_entry["source_task"] = metadata["source_task"]
            skills.append(skill_entry)
        
        return sorted(skills, key=lambda x: x["name"])

    def _read_pattern_metadata(self) -> Dict[str, Dict[str, Any]]:
        """Read pattern metadata for all skills (pattern_name, pattern_description, etc.)."""
        if not self.pattern_metadata_file.exists():
            return {}
        try:
            data = json.loads(self.pattern_metadata_file.read_text())
            return data if isinstance(data, dict) else {}
        except Exception as e:
            logger.warning("Failed to read pattern_metadata.json: %s", e)
            return {}

    def _write_pattern_metadata(self, data: Dict[str, Dict[str, Any]]) -> None:
        """Write pattern metadata dict to disk."""
        self.pattern_metadata_file.write_text(json.dumps(data, indent=2))

    def set_embed_fn(self, embed_fn: Optional[Any]) -> None:
        """Set callable(text: str) -> List[float] for pattern-aware retrieval. Caller provides this."""
        self._embed_fn = embed_fn

    def extract_pattern_metadata(
        self,
        code: str,
        task_description: str,
        llm_callable: Any,
    ) -> Dict[str, Any]:
        """Call LLM to extract pattern abstraction from successful code. Returns dict with pattern_name, pattern_description, key_operations, transfer_conditions."""
        prompt = ABSTRACTION_PROMPT.format(
            successful_code=code[:8000] if len(code) > 8000 else code,
            task_description=(task_description or "")[:2000],
        )
        try:
            response = llm_callable(prompt)
            text = response.strip()
            if "```" in text:
                text = re.sub(r"```(?:json)?\s*", "", text).split("```")[0].strip()
            # Try parse; if malformed (trailing comma, unescaped newline), extract outer {...} by brace count
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                start = text.find("{")
                if start >= 0:
                    depth = 0
                    for i in range(start, len(text)):
                        if text[i] == "{":
                            depth += 1
                        elif text[i] == "}":
                            depth -= 1
                            if depth == 0:
                                try:
                                    return json.loads(text[start : i + 1])
                                except json.JSONDecodeError:
                                    break
                return {}
        except Exception as e:
            logger.warning("Abstraction LLM failed: %s", e)
            return {}

    def extract_and_store_pattern_metadata(
        self,
        skill_name: str,
        code: str,
        task_description: str,
        llm_callable: Any,
    ) -> bool:
        """Extract pattern via LLM and store in pattern_metadata.json. Returns True if stored."""
        if not skill_name or not isinstance(skill_name, str) or skill_name.strip() == "":
            logger.warning("extract_and_store_pattern_metadata: invalid skill_name (%r), skipping", skill_name)
            return False
        meta = self.extract_pattern_metadata(code, task_description, llm_callable)
        if not meta or not meta.get("pattern_description"):
            return False
        data = self._read_pattern_metadata()
        data[skill_name] = {
            "pattern_name": meta.get("pattern_name", ""),
            "pattern_description": meta.get("pattern_description", ""),
            "key_operations": meta.get("key_operations", []),
            "transfer_conditions": meta.get("transfer_conditions", ""),
        }
        self._write_pattern_metadata(data)
        logger.info("Stored pattern metadata for %s: %s", skill_name, meta.get("pattern_name", ""))
        return True

    def get_skills_by_pattern_match(
        self,
        task_description: str,
        top_k: int = 5,
    ) -> List[str]:
        """Return skill names ranked by pattern relevance to task_description. Uses _embed_fn if set."""
        all_names = [s["name"] for s in self.list_skills()]
        if not task_description or not self._embed_fn:
            logger.info("[RUNTIME_DIAG] Pattern retrieval: falling back (no task_description or embed_fn), returning up to %s skills", top_k or "all")
            return all_names[:top_k] if top_k else all_names
        data = self._read_pattern_metadata()
        if not data:
            logger.info("[RUNTIME_DIAG] Pattern retrieval: falling back (no pattern_metadata.json), returning up to %s skills", top_k or "all")
            return all_names[:top_k] if top_k else all_names
        try:
            # Only consider metadata for skills that actually exist (avoids "null" / stale keys)
            valid_names = set(all_names)
            data = {k: v for k, v in data.items() if k in valid_names}
            if not data:
                logger.info("[RUNTIME_DIAG] Pattern retrieval: no metadata for existing skills, returning up to %s", top_k or "all")
                return all_names[:top_k] if top_k else all_names
            logger.info("[RUNTIME_DIAG] Pattern retrieval: using pattern-aware retrieval with %d skills, top_k=%d", len(data), top_k)
            task_emb = self._embed_fn(task_description[:8000])
            if not task_emb:
                return list(data.keys())[:top_k]
            scores: List[Tuple[float, str]] = []
            for name, meta in data.items():
                desc = meta.get("pattern_description", "") or meta.get("transfer_conditions", "")
                if not desc:
                    continue
                skill_emb = self._embed_fn(desc[:8000])
                if not skill_emb:
                    continue
                # Cosine similarity
                a, b = task_emb, skill_emb
                dot = sum(x * y for x, y in zip(a, b))
                na = sum(x * x for x in a) ** 0.5
                nb = sum(y * y for y in b) ** 0.5
                if na and nb:
                    sim = dot / (na * nb)
                    scores.append((sim, name))
            scores.sort(key=lambda x: -x[0])
            names = [name for _, name in scores[:top_k]]
            return names if names else all_names[:top_k]
        except Exception as e:
            logger.warning("Pattern match failed, falling back to all skills: %s", e)
            return all_names[:top_k] if top_k else all_names

    def get_mean_alignment_score(self, task_description: str, top_k: int = 5) -> Optional[float]:
        """
        Return mean cosine similarity of the top-k retrieved skill patterns to task_description.
        Used as a per-task structural alignment metric (high → skills are structurally relevant).
        Returns None if embeddings are unavailable or no pattern metadata exists.
        """
        if not task_description or not self._embed_fn:
            return None
        data = self._read_pattern_metadata()
        all_names = {s["name"] for s in self.list_skills()}
        data = {k: v for k, v in data.items() if k in all_names}
        if not data:
            return None
        try:
            task_emb = self._embed_fn(task_description[:8000])
            if not task_emb:
                return None
            scores: List[float] = []
            for name, meta in data.items():
                desc = meta.get("pattern_description", "") or meta.get("transfer_conditions", "")
                if not desc:
                    continue
                skill_emb = self._embed_fn(desc[:8000])
                if not skill_emb:
                    continue
                a, b = task_emb, skill_emb
                dot = sum(x * y for x, y in zip(a, b))
                na = sum(x * x for x in a) ** 0.5
                nb = sum(y * y for y in b) ** 0.5
                if na and nb:
                    scores.append(dot / (na * nb))
            if not scores:
                return None
            scores.sort(reverse=True)
            top = scores[:top_k]
            return round(sum(top) / len(top), 4)
        except Exception as e:
            logger.warning("get_mean_alignment_score failed: %s", e)
            return None

    def clear_all_skills(self) -> None:
        """Remove all skills (for benchmark condition isolation).
        Preserves __init__.py and resets SKILLS.md / skill_index.json / pattern_metadata.json.
        """
        for skill_file in self.skills_dir.glob("*.py"):
            if skill_file.name != "__init__.py":
                skill_file.unlink()
        self._initialize_skills_file()
        self._write_skill_index([])
        self._write_pattern_metadata({})
        logger.debug("Cleared all skills")

    def delete_skill(self, name: str) -> Dict[str, str]:
        """Delete a skill.
        
        Args:
            name: Skill name
            
        Returns:
            Dictionary with status
            
        Raises:
            ValueError: If skill doesn't exist
        """
        skill_file = self.skills_dir / f"{name}.py"
        
        if not skill_file.exists():
            raise ValueError(f"Skill '{name}' not found")
        
        # Delete file
        skill_file.unlink()
        
        # Remove from pattern metadata if present
        data = self._read_pattern_metadata()
        if name in data:
            del data[name]
            self._write_pattern_metadata(data)
        
        # Remove from SKILLS.md
        self._remove_skill_from_registry(name)
        
        # Update skill_index.json
        self._update_skill_index()
        
        logger.info(f"Deleted skill '{name}'")
        
        return {
            "status": "success",
            "name": name,
            "message": f"Skill '{name}' deleted successfully"
        }
    
    def search_skills(self, query: str) -> List[Dict[str, str]]:
        """Search skills by name, description, or tags.
        
        Args:
            query: Search query
            
        Returns:
            List of matching skills
        """
        all_skills = self.list_skills()
        query_lower = query.lower()
        
        matching_skills = []
        for skill in all_skills:
            # Check if query matches name, description, or tags
            if (query_lower in skill["name"].lower() or
                query_lower in skill["description"].lower() or
                query_lower in skill["tags"].lower()):
                matching_skills.append(skill)
        
        return matching_skills

    def get_skill_listing(
        self,
        skill_names: Optional[List[str]] = None,
        task_description: Optional[str] = None,
        top_k: int = 5,
        include_full_code: bool = False,
    ) -> str:
        """Get a formatted string of available skills for prompt injection.
        
        Args:
            skill_names: If provided, only list these skills (for condition isolation).
            task_description: If provided and _embed_fn is set, use pattern-aware retrieval (top_k skills by relevance).
            top_k: Max number of skills to return when using pattern-aware retrieval.
            include_full_code: If True, inject full skill code (like oracle) instead of name/description only.
        """
        skills = self.list_skills()
        if task_description and self._embed_fn and skill_names is None:
            top_names = self.get_skills_by_pattern_match(task_description, top_k=top_k)
            names_set = set(top_names)
            skills = [s for s in skills if s["name"] in names_set]
            skills.sort(key=lambda s: top_names.index(s["name"]) if s["name"] in top_names else 999)
        elif skill_names is not None:
            names_set = set(skill_names)
            skills = [s for s in skills if s["name"] in names_set]
        if not skills:
            return ""

        if include_full_code:
            header = (
                "\n# Relevant skills from prior tasks (pattern-matched). Adapt as needed.\n"
            )
            parts = [header]
            for skill in skills:
                try:
                    data = self.get_skill(skill["name"])
                    code = data.get("code", "")
                    if code:
                        parts.append(f"# --- {skill['name']} ---\n{code}\n")
                except Exception:
                    continue
            return "\n".join(parts) if len(parts) > 1 else ""
            
        lines = ["# Available skills (importable as `from skills.X import run`):"]
        for skill in skills:
            signature = "(...)"
            try:
                # Try to extract signature from code
                skill_data = self.get_skill(skill["name"])
                code = skill_data.get("code", "")
                
                run_match = re.search(r'def\s+run\s*\([^)]*\)(?:\s*->\s*[^:]+)?', code)
                if run_match:
                    signature = run_match.group(0).replace('def run', '').strip()
                else:
                    # Fallback to last defined function
                    func_match = re.findall(r'def\s+([a-zA-Z0-9_]+)\s*\([^)]*\)', code)
                    if func_match:
                        def_match = re.search(rf'def\s+{func_match[-1]}\s*\([^)]*\)(?:\s*->\s*[^:]+)?', code)
                        if def_match:
                            signature = def_match.group(0).replace(f'def {func_match[-1]}', '').strip()
            except Exception:
                pass
                
            desc = skill.get("description", "No description")
            name = skill["name"]
            
            # Keep description on the same line but neatly formatted
            lines.append(f"# - {name}{signature} — {desc}")
            
        return "\n".join(lines)
        
    def is_worth_saving(self, code: str, output: Any = None) -> bool:
        """Heuristic to determine if a generic code snippet is worth saving as a tool.
        
        Checks if:
        1. Code compiles (Python) OR is valid SQL
        2. Code defines at least one reusable function (Python) OR has SQL structure
        3. Produced structured/sizable output (if output provided)
        """
        code_stripped = code.strip()
        if not code_stripped:
            return False
        
        # Check if this looks like SQL (has SQL keywords at start)
        upper = code_stripped.upper()
        sql_keywords = ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'WITH', 'ALTER', 'DROP')
        looks_like_sql = upper.startswith(sql_keywords) or any(
            re.search(rf'\b{kw}\b', upper) for kw in sql_keywords[:3]
        )
        
        if looks_like_sql:
            # Validate SQL has minimal structure
            has_from = 'FROM' in upper
            has_select = 'SELECT' in upper
            # Must have SELECT and either FROM or a valid subquery pattern
            if has_select and (has_from or 'WITH' in upper):
                # SQL is valid enough - check output like Python
                if output is not None:
                    if isinstance(output, (dict, list)):
                        return True
                    if isinstance(output, str) and len(output.strip()) > 0:
                        return True
                    if isinstance(output, (int, float)):
                        return True
                    return False
                return True
            return False
        
        # Python code path - original logic
        try:
            tree = ast.parse(code)
            has_func = any(isinstance(node, ast.FunctionDef) for node in ast.walk(tree))
            if not has_func:
                return False
                
            # If output is available, check if it's somewhat structured/interesting
            if output is not None:
                # Dictionaries and lists are definitely useful
                if isinstance(output, (dict, list)):
                    return True
                # Long strings probably indicate successful parsing or extraction
                if isinstance(output, str) and len(output.strip()) > 10:
                    return True
                # Numbers are OK too
                if isinstance(output, (int, float)):
                    return True
                return False
                
            return True
        except Exception:
            # If it fails to parse, not worth saving
            return False

    def extract_skill_from_code(self, code: str, name: str, description: str) -> str:
        """Extract a canonical skill structure from raw code.
        
        Wraps code into a standard module with a run() entry-point and metadata.
        """
        header = f'''"""
skill_name: {name}
description: {description}
Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Tags: auto-generated, agent-skill
"""

'''
        try:
            tree = ast.parse(code)
            funcs = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
            
            if "run" in funcs:
                return header + code
                
            if funcs:
                # It has a function but no run(). Let's alias the last defined function.
                # Usually scripts define a main worker function at the bottom.
                main_func = funcs[-1]
                return header + code + f'\n\n# Auto-generated entry-point\nrun = {main_func}\n'
            
            # No functions at all - just a flat script. Wrap it in a run()
            indented_code = "\n".join("    " + line for line in code.split("\n"))
            return header + f'def run(*args, **kwargs):\n{indented_code}\n    return locals().get("result", None)\n'
            
        except SyntaxError:
            # Fallback for syntactically invalid code if any
            return header + code
    
    def _is_valid_skill_name(self, name: str) -> bool:
        """Check if skill name is a valid Python identifier."""
        return name.isidentifier() and not name.startswith("_")
    
    def _extract_metadata(self, code: str) -> Dict[str, str]:
        """Extract metadata from skill docstring."""
        metadata = {}
        
        # Extract module docstring
        lines = code.split('\n')
        if lines and lines[0].startswith('"""'):
            docstring_lines = []
            for i, line in enumerate(lines[1:], 1):
                if '"""' in line:
                    break
                docstring_lines.append(line)
            
            docstring = '\n'.join(docstring_lines)
            
            # If it matches the new format with explicit keys:
            name_match = re.search(r'skill_name:\s*(.+)', docstring)
            if name_match:
                metadata['name'] = name_match.group(1).strip()
                
            desc_match = re.search(r'description:\s*(.+)', docstring)
            if desc_match:
                metadata['description'] = desc_match.group(1).strip()
            
            # Extract created date
            created_match = re.search(r'Created:\s*(.+)', docstring)
            if created_match:
                metadata['created'] = created_match.group(1).strip()
            
            # Extract tags
            tags_match = re.search(r'Tags:\s*(.+)', docstring)
            if tags_match:
                metadata['tags'] = tags_match.group(1).strip()

            # Extract source_task (optional, used by benchmarks)
            source_match = re.search(r'source_task:\s*(.+)', docstring)
            if source_match:
                metadata['source_task'] = source_match.group(1).strip()
                
            # If description wasn't found via key, fallback to finding first non-empty line
            if 'description' not in metadata:
                for line in docstring_lines:
                    line = line.strip()
                    if line and not line.startswith('Created:') and not line.startswith('Tags:') and not line.startswith('skill_name:'):
                        metadata['description'] = line
                        break
        
        return metadata
    
    def _add_skill_to_registry(self, name: str, description: str, tags: List[str]) -> None:
        """Add skill entry to SKILLS.md."""
        content = self.skills_file.read_text()
        
        # Find the skills section
        start_marker = "<!--SKILLS_START-->"
        end_marker = "<!--SKILLS_END-->"
        
        if start_marker in content and end_marker in content:
            start_idx = content.index(start_marker) + len(start_marker)
            end_idx = content.index(end_marker)
            
            # Create skill entry
            tags_str = f" `{', '.join(tags)}`" if tags else ""
            entry = f"\n### {name}{tags_str}\n\n{description}\n\n```python\nfrom skills.{name} import run\n```\n"
            
            # Insert entry
            new_content = (
                content[:start_idx] +
                entry +
                content[end_idx:]
            )
            
            self.skills_file.write_text(new_content)
    
    def _remove_skill_from_registry(self, name: str) -> None:
        """Remove skill entry from SKILLS.md."""
        content = self.skills_file.read_text()
        
        # Remove the skill section (### name ... until next ### or end marker)
        pattern = rf"### {re.escape(name)}.*?(?=###|<!--SKILLS_END-->)"
        new_content = re.sub(pattern, "", content, flags=re.DOTALL)
        
        self.skills_file.write_text(new_content)

    def _write_skill_index(self, skills: List[Dict[str, str]]) -> None:
        """Write the skill_index.json manifest file."""
        import json
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(skills, f, indent=2)

    def _update_skill_index(self) -> None:
        """Regenerate and write the skill_index.json based on current exact files."""
        skills = self.list_skills()
        self._write_skill_index(skills)
