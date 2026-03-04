"""Example 17: Skill Evolution (Self-Growing Tool Library).

Demonstrates the closed-loop "Skill Evolution" architecture where the agent
acts as both a domain expert and a toolsmith:
1. Agent generates a successful code action for a novel task.
2. The code action is automatically saved as a typed, callable skill.
3. In a future session, the agent discovers and reuses this skill directly
   instead of re-implementing the logic.

Requires:
    msb server start --dev
"""

import os
import sys
import shutil
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from client.agent_helper import AgentHelper
from client.filesystem_helpers import FilesystemHelper
from client.sandbox_executor import MicrosandboxExecutor
from client.skill_manager import SkillManager
from config.loader import load_config


def print_header(title: str):
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80 + "\n")


def cleanup_skills(skills_dir: Path):
    """Clean up the skills directory before the demo."""
    if skills_dir.exists():
        for file in skills_dir.glob("*.py"):
            if file.name != "__init__.py":
                file.unlink()
        
        index_file = skills_dir / "skill_index.json"
        if index_file.exists():
            index_file.unlink()
            
        md_file = skills_dir / "SKILLS.md"
        if md_file.exists():
            md_file.unlink()
            
    print(f"🧹 Cleaned up skills directory: {skills_dir}")


def main():
    print_header("Skill Evolution: Evolving a Tool Library")
    
    config = load_config()
    
    # We require an LLM for this demo to show prompt injection
    if not config.llm.enabled:
        print("❌ This demo requires LLM code generation to be enabled.")
        print("   Please set llm.enabled = true in your config.toml")
        return

    # 1. Setup Phase
    workspace_dir = Path(config.execution.workspace_dir)
    skills_dir = workspace_dir / "skills"
    
    cleanup_skills(skills_dir)
    
    fs_helper = FilesystemHelper(
        workspace_dir=config.execution.workspace_dir,
        servers_dir=config.execution.servers_dir,
        skills_dir=config.execution.skills_dir,
    )

    executor = MicrosandboxExecutor(
        execution_config=config.execution,
        guardrail_config=config.guardrails,
        optimization_config=config.optimizations,
    )
    
    # Create the SkillManager
    skill_manager = SkillManager(workspace_dir=str(workspace_dir))
    
    print("🤖 Agent Initialized with Skill Evolution (auto_save_skills=True)")
    
    # ------------------------------------------------------------------
    # Turn 1: Novel Task -> Code Action -> Evolved Skill
    # ------------------------------------------------------------------
    print_header("TURN 1: Novel Task creates a new Skill")
    
    # We use AgentHelper with the skill_manager attached
    agent1 = AgentHelper(
        fs_helper=fs_helper,
        executor=executor,
        llm_config=config.llm,
        optimization_config=config.optimizations,
        skill_manager=skill_manager,
        auto_save_skills=True  # This is the magic flag!
    )
    
    task1 = "Create a function called count_vowels that takes a string and returns the number of vowels in it. Test it with the string 'Skill Evolution is amazing'."
    
    print(f"User: {task1}\n")
    agent1.execute_task(task_description=task1, verbose=True)
    
    # Verify the skill was saved
    skills = skill_manager.list_skills()
    print(f"\n📁 Skills in registry after Turn 1: {[s['name'] for s in skills]}")
    
    time.sleep(2)
    
    # ------------------------------------------------------------------
    # Turn 2: Future Session -> Reuses the Evolved Skill
    # ------------------------------------------------------------------
    print_header("TURN 2: Future session reuses the evolved skill")
    
    print("🔄 Simulating a new agent session (but using the same skills directory)...\n")
    
    # We create a fresh AgentHelper to simulate a new turn/session.
    # It will automatically discover the skill saved in Turn 1.
    agent2 = AgentHelper(
        fs_helper=fs_helper,
        executor=executor,
        llm_config=config.llm,
        optimization_config=config.optimizations,
        skill_manager=skill_manager,
        auto_save_skills=True
    )
    
    task2 = "Use the generic skill you have available to count the vowels in the string 'MCPRuntime learning new tricks'."
    
    print(f"User: {task2}\n")
    agent2.execute_task(task_description=task2, verbose=True)
    
    print_header("Demo Complete!")
    print(f"Check out the generated skill module at: {skills_dir}")


if __name__ == "__main__":
    main()
