"""Skill management for AgentKernel.

This module allows agents to save, discover, and reuse code patterns as "skills".
Skills are saved as Python modules in the workspace/skills/ directory with
metadata tracked in SKILLS.md for discovery.

Based on Anthropic's "Skills" pattern from:
https://www.anthropic.com/engineering/code-execution-with-mcp
"""

import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class SkillManager:
    """Manages reusable code skills for agents.
    
    Skills are Python functions/modules that agents have created and can
    reuse across sessions. Each skill includes:
    - Python code (saved as .py file)
    - Description (saved in SKILLS.md)
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
        
        # Create skills directory if it doesn't exist
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        
        # Create __init__.py to make it a package
        init_file = self.skills_dir / "__init__.py"
        if not init_file.exists():
            init_file.write_text('"""Agent skills package."""\n')
        
        # Create SKILLS.md if it doesn't exist
        if not self.skills_file.exists():
            self._initialize_skills_file()
    
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
from skills import skill_name
result = skill_name.function_name(args)
```

## Skill Format

Each skill should:
1. Have a clear, descriptive name
2. Include docstrings explaining what it does
3. Be self-contained (minimal external dependencies)
4. Return results rather than printing them
"""
        self.skills_file.write_text(content)
    
    def save_skill(
        self,
        name: str,
        code: str,
        description: str,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """Save a new skill.
        
        Args:
            name: Skill name (must be valid Python identifier)
            code: Python code for the skill
            description: Human-readable description
            tags: Optional list of tags for categorization
            
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
                f"Skill '{name}' already exists. Use delete_skill() first to replace it."
            )
        
        # Add header comment to code
        header = f'''"""
{description}

Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Tags: {', '.join(tags or [])}
"""

'''
        full_code = header + code
        
        # Save skill file
        skill_file.write_text(full_code)
        
        # Update SKILLS.md
        self._add_skill_to_registry(name, description, tags or [])
        
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
            
            skills.append({
                "name": name,
                "description": metadata.get("description", "No description"),
                "tags": metadata.get("tags", ""),
                "created": metadata.get("created", "Unknown"),
                "path": str(skill_file)
            })
        
        return sorted(skills, key=lambda x: x["name"])
    
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
            in_docstring = True
            for i, line in enumerate(lines[1:], 1):
                if '"""' in line:
                    break
                docstring_lines.append(line)
            
            docstring = '\n'.join(docstring_lines)
            
            # Extract description (first non-empty line)
            for line in docstring_lines:
                line = line.strip()
                if line and not line.startswith('Created:') and not line.startswith('Tags:'):
                    metadata['description'] = line
                    break
            
            # Extract created date
            created_match = re.search(r'Created:\s*(.+)', docstring)
            if created_match:
                metadata['created'] = created_match.group(1).strip()
            
            # Extract tags
            tags_match = re.search(r'Tags:\s*(.+)', docstring)
            if tags_match:
                metadata['tags'] = tags_match.group(1).strip()
        
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
            entry = f"\n### {name}{tags_str}\n\n{description}\n\n```python\nfrom skills import {name}\n```\n"
            
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
