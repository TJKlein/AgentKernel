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
    
    def clear_all_skills(self) -> None:
        """Remove all skills (for benchmark condition isolation).
        Preserves __init__.py and resets SKILLS.md / skill_index.json.
        """
        for skill_file in self.skills_dir.glob("*.py"):
            if skill_file.name != "__init__.py":
                skill_file.unlink()
        self._initialize_skills_file()
        self._write_skill_index([])
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

    def get_skill_listing(self, skill_names: Optional[List[str]] = None) -> str:
        """Get a formatted string of available skills for prompt injection.
        
        Args:
            skill_names: If provided, only list these skills (for condition isolation).
        """
        skills = self.list_skills()
        if skill_names is not None:
            names_set = set(skill_names)
            skills = [s for s in skills if s["name"] in names_set]
        if not skills:
            return ""
            
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
