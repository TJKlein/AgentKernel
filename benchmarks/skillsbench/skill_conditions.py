"""
Skill Conditions Management

Implements the 4 conditions for SkillsBench evaluation:
1. NO_SKILLS: Baseline - no skills provided
2. CURATED_SKILLS: Human-written skills provided with task
3. SELF_GENERATED_SKILLS: Model generates skills BEFORE task (speculation-based)
4. RUNTIME_EVOLVED_SKILLS: Skills generated AFTER successful execution (execution-grounded)

The key distinction between condition 3 and 4:
- Self-generated: Skills created speculatively before seeing if they work
- Runtime-evolved: Skills created from code that has already been verified to work

This module manages switching between conditions and tracking skill provenance.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path

from client.skill_manager import SkillManager

logger = logging.getLogger(__name__)


class SkillCondition(Enum):
    """Skill conditions for SkillsBench + MCPRuntime + ConceptDriftBench."""
    NO_SKILLS = auto()
    CURATED_SKILLS = auto()
    SELF_GENERATED_SKILLS = auto()
    RUNTIME_EVOLVED_SKILLS = auto()
    ORACLE_RETRIEVAL = auto()       # ConceptDrift: correct prior skill provided
    CROSS_FAMILY = auto()           # ConceptDrift: all accumulated skills available
    
    def __str__(self) -> str:
        return self.name.lower()


@dataclass
class SkillProvenance:
    """Tracks how a skill was created and its quality metrics."""
    skill_name: str
    condition: SkillCondition
    source_task: str
    creation_time: float
    
    # For runtime-evolved skills
    execution_verified: bool = False
    execution_output: Any = None
    code_quality_score: float = 0.0
    
    # For self-generated skills
    generation_prompt: str = ""
    generation_iterations: int = 0
    
    # Reuse tracking
    times_reused: int = 0
    reuse_history: List[Dict[str, Any]] = field(default_factory=list)


class ConditionManager:
    """
    Manages the 4 skill conditions for SkillsBench evaluation.
    
    For each task run, the agent operates under one of the 4 conditions.
    This class handles:
    - Setting up the appropriate skill context for each condition
    - Managing the skill lifecycle for runtime-evolved skills
    - Tracking skill provenance and reuse
    - Providing comparative metrics between conditions
    """
    
    def __init__(
        self,
        condition: SkillCondition,
        skill_manager: Optional[SkillManager] = None,
        workspace_dir: Optional[str] = None,
    ):
        """
        Initialize condition manager.
        
        Args:
            condition: Which of the 4 conditions to use
            skill_manager: SkillManager instance (required for RUNTIME_EVOLVED)
            workspace_dir: Workspace directory for skill storage
        """
        self.condition = condition
        self.skill_provenance: Dict[str, SkillProvenance] = {}
        
        if skill_manager:
            self.skill_manager = skill_manager
        elif workspace_dir:
            self.skill_manager = SkillManager(workspace_dir)
        else:
            self.skill_manager = None
            
        self._curated_skills: Dict[str, str] = {}  # task_id -> skill_content
        self._self_generated_skills: Dict[str, str] = {}  # task_id -> skill_content
        self._oracle_skills: Dict[str, str] = {}  # task_id -> skill_content from prior task
        
        logger.info(f"ConditionManager initialized with condition: {condition.name}")
    
    def get_skill_context(self, task_id: str) -> str:
        """
        Get the skill context to inject for the current condition.
        
        Returns:
            String to add to the agent's prompt context
        """
        if self.condition == SkillCondition.NO_SKILLS:
            return ""
            
        elif self.condition == SkillCondition.CURATED_SKILLS:
            skill = self._curated_skills.get(task_id, "")
            if skill:
                return f"\n# Available skill for this task:\n{skill}\n"
            return ""
            
        elif self.condition == SkillCondition.SELF_GENERATED_SKILLS:
            skill = self._self_generated_skills.get(task_id, "")
            if skill:
                return f"\n# Self-generated skill available:\n{skill}\n"
            return ""
            
        elif self.condition == SkillCondition.RUNTIME_EVOLVED_SKILLS:
            if self.skill_manager:
                return self.skill_manager.get_skill_listing()
            return ""

        elif self.condition == SkillCondition.ORACLE_RETRIEVAL:
            # Show ONLY the specific oracle skill for this task
            # The oracle skill is saved with the task's own ID (e.g., oracle_c2 for task C2)
            # Extract the task prefix from task_id (e.g., "C2" from "C2_spider2_works_cycles")
            task_prefix = task_id.split('_')[0] if '_' in task_id else task_id
            oracle_skill_name = f"oracle_{task_prefix.lower()}"
            
            # Try to get from skill_manager first
            if self.skill_manager:
                all_skills = self.skill_manager.list_skills()
                if any(s["name"] == oracle_skill_name for s in all_skills):
                    return self.skill_manager.get_skill_listing(
                        skill_names=[oracle_skill_name]
                    )
            
            # Fallback to raw code from _oracle_skills
            oracle_code = self._oracle_skills.get(task_id) or self._oracle_skills.get(task_prefix, "")
            if oracle_code:
                return (
                    "\n# A skill from a related prior task is available below.\n"
                    "# It may or may not be directly applicable — adapt as needed.\n"
                    f"{oracle_code}\n"
                )
            return ""

        elif self.condition == SkillCondition.CROSS_FAMILY:
            if self.skill_manager:
                return self.skill_manager.get_skill_listing()
            return ""

        return ""
    
    def set_curated_skill(self, task_id: str, skill_content: str) -> None:
        """Set the curated skill for a task (condition 2)."""
        self._curated_skills[task_id] = skill_content

    def curated_skill_count(self) -> int:
        """Return how many tasks have curated skill content (for metrics)."""
        return len(self._curated_skills)

    def set_oracle_skill(self, task_id: str, skill_content: str) -> None:
        """Set the oracle skill for a ConceptDrift task (ORACLE_RETRIEVAL condition)."""
        self._oracle_skills[task_id] = skill_content
        
    def set_self_generated_skill(
        self,
        task_id: str,
        skill_content: str,
        generation_prompt: str = "",
        iterations: int = 0,
    ) -> None:
        """
        Set a self-generated skill for a task (condition 3).
        
        This represents the speculation-based skill generation where the model
creates skills before task execution without knowing if they'll work.
        """
        self._self_generated_skills[task_id] = skill_content
        
        # Track provenance
        import time
        self.skill_provenance[task_id] = SkillProvenance(
            skill_name=f"sg_{task_id}",
            condition=SkillCondition.SELF_GENERATED_SKILLS,
            source_task=task_id,
            creation_time=time.time(),
            generation_prompt=generation_prompt,
            generation_iterations=iterations,
        )
    
    def extract_and_save_runtime_skill(
        self,
        task_id: str,
        code: str,
        output: Any,
        description: str,
    ) -> Optional[str]:
        """
        Extract and save a runtime-evolved skill (condition 4).
        
        This is the key MCPRuntime differentiator: skills are extracted from
        code that has ALREADY BEEN VERIFIED to work successfully. This makes
them execution-grounded rather than speculation-based.
        
        Args:
            task_id: The task that produced the skill
            code: The successful code execution
            output: The execution output
            description: Skill description
            
        Returns:
            Skill name if saved, None otherwise
        """
        if not self.skill_manager:
            logger.warning("No skill manager available for runtime skill extraction")
            return None
            
        if not self.condition == SkillCondition.RUNTIME_EVOLVED_SKILLS:
            logger.debug("Not in runtime-evolved condition, skipping skill save")
            return None
        
        # Use skill manager to extract and save
        skill_name = f"rt_{task_id.lower()}"
        
        try:
            # Check if worth saving
            if not self.skill_manager.is_worth_saving(code, output):
                logger.debug(f"Code not worth saving as skill for {task_id}")
                return None
            
            # Extract skill from code
            skill_code = self.skill_manager.extract_skill_from_code(
                code=code,
                name=skill_name,
                description=description,
            )
            
            # Save or update skill (use update_skill if it already exists, e.g., from pre-run)
            skill_file = self.skill_manager.skills_dir / f"{skill_name}.py"
            if skill_file.exists():
                self.skill_manager.update_skill(
                    name=skill_name,
                    code=skill_code,
                    description=description,
                    tags=["runtime-evolved", task_id],
                )
            else:
                self.skill_manager.save_skill(
                    name=skill_name,
                    code=skill_code,
                    description=description,
                    tags=["runtime-evolved", task_id],
                    source_task=task_id,
                )
            
            # Track provenance
            import time
            self.skill_provenance[skill_name] = SkillProvenance(
                skill_name=skill_name,
                condition=SkillCondition.RUNTIME_EVOLVED_SKILLS,
                source_task=task_id,
                creation_time=time.time(),
                execution_verified=True,
                execution_output=output,
            )
            
            logger.info(f"💡 Runtime-evolved skill saved: {skill_name}")
            return skill_name
            
        except Exception as e:
            logger.warning(f"Failed to save runtime skill for {task_id}: {e}")
            return None
    
    def track_skill_reuse(
        self,
        skill_name: str,
        task_id: str,
        code_snippet: str,
    ) -> None:
        """Track when a skill is reused in a subsequent task."""
        if skill_name in self.skill_provenance:
            prov = self.skill_provenance[skill_name]
            prov.times_reused += 1
            import time
            prov.reuse_history.append({
                "task": task_id,
                "timestamp": time.time(),
                "code_snippet": code_snippet,
            })
            logger.info(f"🔄 Skill '{skill_name}' reused in task {task_id}")
    
    def get_condition_description(self) -> str:
        """Get human-readable description of the current condition."""
        descriptions = {
            SkillCondition.NO_SKILLS: (
                "No Skills (Baseline): Agent operates without any pre-defined skills. "
                "This measures raw capability without skill augmentation."
            ),
            SkillCondition.CURATED_SKILLS: (
                "Curated Skills: Human-written skills are provided with each task. "
                "This measures performance with expert-crafted procedural knowledge."
            ),
            SkillCondition.SELF_GENERATED_SKILLS: (
                "Self-Generated Skills: Model generates skills BEFORE task execution "
                "(speculation-based). Skills are not verified to work before use. "
                "This is what SkillsBench showed provides no average benefit."
            ),
            SkillCondition.RUNTIME_EVOLVED_SKILLS: (
                "Runtime-Evolved Skills (MCPRuntime): Skills are extracted AFTER "
                "successful code execution (execution-grounded). They contain real "
                "imports, real signatures, real outputs - not speculation. "
                "This is the novel contribution: grounded skill evolution."
            ),
            SkillCondition.ORACLE_RETRIEVAL: (
                "Oracle Retrieval (ConceptDrift): The correct skill from the "
                "immediately prior task in the family is provided. The agent "
                "must decide whether and how to adapt it. This diagnostic "
                "condition separates retrieval quality from adaptation quality."
            ),
            SkillCondition.CROSS_FAMILY: (
                "Cross-Family (ConceptDrift): All accumulated skills from every "
                "family are available. Tests whether skills transfer across "
                "families and whether composition emerges naturally."
            ),
        }
        return descriptions.get(self.condition, "Unknown condition")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get metrics for skills under this condition."""
        metrics = {
            "condition": self.condition.name,
            "total_skills": len(self.skill_provenance),
            "description": self.get_condition_description(),
        }
        
        if self.condition == SkillCondition.RUNTIME_EVOLVED_SKILLS:
            verified = sum(1 for p in self.skill_provenance.values() if p.execution_verified)
            total_reuses = sum(p.times_reused for p in self.skill_provenance.values())
            
            metrics.update({
                "verified_skills": verified,
                "total_reuses": total_reuses,
                "avg_reuses_per_skill": total_reuses / len(self.skill_provenance) if self.skill_provenance else 0,
            })
            
        elif self.condition == SkillCondition.SELF_GENERATED_SKILLS:
            avg_iterations = sum(
                p.generation_iterations 
                for p in self.skill_provenance.values()
            ) / len(self.skill_provenance) if self.skill_provenance else 0
            
            metrics.update({
                "avg_generation_iterations": avg_iterations,
            })
        
        return metrics


class SelfGeneratedSkillFactory:
    """
    Factory for creating self-generated skills (condition 3).
    
    This simulates the SkillsBench self-generated skills condition where
the model attempts to generate useful skills BEFORE seeing the task
execution. This is speculation-based generation.
    """
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        
    def generate_skill_for_task(
        self,
        task_description: str,
        task_category: str,
        max_attempts: int = 3,
    ) -> Optional[str]:
        """
        Generate a skill for a task BEFORE execution (speculation-based).
        
        This mimics what SkillsBench tests: can the model predict what
        skills would be useful and generate them correctly before seeing
        if they actually work?
        
        Args:
            task_description: Description of the task
            task_category: Category of the task
            max_attempts: Maximum generation attempts
            
        Returns:
            Generated skill code or None if generation failed
        """
        if not self.llm_client:
            # Fallback: return empty (represents failed self-generation)
            return None
        
        prompt = f"""You are an expert at creating reusable agent skills.

Given the following task description and category, create a Python skill
that would help an AI agent complete this type of task efficiently.

Task Category: {task_category}
Task Description: {task_description}

Create a Python module with:
1. A clear docstring explaining what the skill does
2. A `run(*args, **kwargs)` function as the entry point
3. Any helper functions needed
4. Proper error handling

The skill should be general enough to handle similar tasks but specific
enough to be immediately useful.

Return only the Python code, no explanation.
"""
        system = "You are an expert at creating reusable Python skills for AI agents. Return only valid Python code, no markdown or explanation."
        for attempt in range(max_attempts):
            try:
                if not self.llm_client or not hasattr(self.llm_client, "generate_from_prompt"):
                    return None
                raw = self.llm_client.generate_from_prompt(
                    system_content=system,
                    user_content=prompt,
                    max_tokens=2048,
                )
                if not raw or not raw.strip():
                    continue
                # Strip markdown code blocks if present
                code = raw.strip()
                if code.startswith("```python"):
                    code = code[9:]
                elif code.startswith("```"):
                    code = code[3:]
                if code.endswith("```"):
                    code = code[:-3]
                code = code.strip()
                if code:
                    return code
            except Exception as e:
                logger.warning(f"Skill generation attempt {attempt + 1} failed: {e}")
                continue
        return None
