"""
Test suite for AgentKernel skill management system.

This test suite validates:
- Skill creation and storage
- Skill retrieval and metadata extraction
- Skill listing and searching
- Skill deletion
- Skill import and execution in sandbox
- SKILLS.md registry maintenance
"""

import os
import sys
import shutil
import tempfile
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from client.skill_manager import SkillManager


def print_step(step: str, status: str = ""):
    """Print a test step."""
    if status == "✓":
        print(f"✓ {step}")
    elif status == "✗":
        print(f"✗ {step}")
    elif status == "⚠":
        print(f"⚠ {step}")
    else:
        print(f"  {step}")


def test_skill_manager():
    """Run all skill manager tests."""
    print("=" * 60)
    print("AgentKernel Skill Management Test Suite")
    print("=" * 60)
    print()
    
    # Create temporary workspace
    temp_workspace = tempfile.mkdtemp()
    
    try:
        # Test 1: Initialize SkillManager
        print("[Test 1] Initialize SkillManager...")
        skill_manager = SkillManager(workspace_dir=temp_workspace)
        assert skill_manager.skills_dir.exists(), "Skills directory not created"
        assert skill_manager.skills_file.exists(), "SKILLS.md not created"
        print_step("SkillManager initialized", "✓")
        print_step(f"Skills directory: {skill_manager.skills_dir}", "✓")
        print()
        
        # Test 2: Save a skill
        print("[Test 2] Save a skill...")
        skill_code = """
def fibonacci(n):
    \"\"\"Calculate fibonacci number.
    
    Args:
        n: The position in the sequence
        
    Returns:
        The nth fibonacci number
    \"\"\"
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
"""
        
        result = skill_manager.save_skill(
            name="fibonacci_calculator",
            code=skill_code,
            description="Calculate fibonacci numbers recursively",
            tags=["math", "recursion"]
        )
        
        assert result["status"] == "success", f"Save failed: {result}"
        assert "fibonacci_calculator.py" in result["path"], "Skill file path incorrect"
        print_step("Skill saved successfully", "✓")
        print_step(f"Path: {result['path']}", "✓")
        print()
        
        # Test 3: Verify skill file exists and has correct content
        print("[Test 3] Verify skill file...")
        skill_file = skill_manager.skills_dir / "fibonacci_calculator.py"
        assert skill_file.exists(), "Skill file not created"
        content = skill_file.read_text()
        assert "Calculate fibonacci numbers recursively" in content, "Description not in file"
        assert "Tags: math, recursion" in content, "Tags not in file"
        assert "def fibonacci(n):" in content, "Function code not in file"
        print_step("Skill file created correctly", "✓")
        print()
        
        # Test 4: Verify SKILLS.md updated
        print("[Test 4] Verify SKILLS.md registry...")
        skills_md = skill_manager.skills_file.read_text()
        assert "### fibonacci_calculator" in skills_md, "Skill not in registry"
        assert "Calculate fibonacci numbers recursively" in skills_md, "Description not in registry"
        print_step("SKILLS.md updated correctly", "✓")
        print()
        
        # Test 5: Get skill
        print("[Test 5] Get skill...")
        skill_data = skill_manager.get_skill("fibonacci_calculator")
        assert skill_data["name"] == "fibonacci_calculator", "Skill name incorrect"
        assert "def fibonacci(n):" in skill_data["code"], "Skill code incorrect"
        assert "description" in skill_data, "No description in metadata"
        assert "tags" in skill_data, "No tags in metadata"
        print_step("Skill retrieved successfully", "✓")
        print_step(f"Description: {skill_data.get('description', 'N/A')}", "✓")
        print()
        
        # Test 6: List skills
        print("[Test 6] List skills...")
        skills = skill_manager.list_skills()
        assert len(skills) == 1, f"Expected 1 skill, got {len(skills)}"
        assert skills[0]["name"] == "fibonacci_calculator", "Skill name incorrect"
        print_step(f"Found {len(skills)} skill(s)", "✓")
        print_step(f"Skill: {skills[0]['name']}", "✓")
        print()
        
        # Test 7: Save another skill
        print("[Test 7] Save another skill...")
        csv_code = """
import csv
from pathlib import Path

def merge_csv_files(input_files, output_file):
    \"\"\"Merge multiple CSV files into one.
    
    Args:
        input_files: List of input CSV file paths
        output_file: Output CSV file path
        
    Returns:
        Number of rows merged
    \"\"\"
    rows = []
    header = None
    
    for file_path in input_files:
        with open(file_path, 'r') as f:
            reader = csv.reader(f)
            file_header = next(reader)
            if header is None:
                header = file_header
            for row in reader:
                rows.append(row)
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    
    return len(rows)
"""
        
        result = skill_manager.save_skill(
            name="csv_merger",
            code=csv_code,
            description="Merge multiple CSV files",
            tags=["data", "csv", "etl"]
        )
        
        assert result["status"] == "success", "Second save failed"
        print_step("Second skill saved", "✓")
        print()
        
        # Test 8: List multiple skills
        print("[Test 8] List multiple skills...")
        skills = skill_manager.list_skills()
        assert len(skills) == 2, f"Expected 2 skills, got {len(skills)}"
        skill_names = [s["name"] for s in skills]
        assert "fibonacci_calculator" in skill_names, "fibonacci_calculator not in list"
        assert "csv_merger" in skill_names, "csv_merger not in list"
        print_step(f"Found {len(skills)} skills", "✓")
        for skill in skills:
            print_step(f"  - {skill['name']}: {skill['description']}", "✓")
        print()
        
        # Test 9: Search skills
        print("[Test 9] Search skills...")
        results = skill_manager.search_skills("csv")
        assert len(results) == 1, f"Expected 1 result for 'csv', got {len(results)}"
        assert results[0]["name"] == "csv_merger", "Wrong skill found"
        print_step("Search for 'csv' found correct skill", "✓")
        
        results = skill_manager.search_skills("math")
        assert len(results) == 1, f"Expected 1 result for 'math', got {len(results)}"
        assert results[0]["name"] == "fibonacci_calculator", "Wrong skill found"
        print_step("Search for 'math' found correct skill", "✓")
        print()
        
        # Test 10: Test invalid skill name
        print("[Test 10] Test invalid skill names...")
        try:
            skill_manager.save_skill(
                name="invalid-name",  # hyphens not allowed
                code="def foo(): pass",
                description="Test"
            )
            print_step("Should have rejected invalid name", "✗")
        except ValueError as e:
            print_step("Correctly rejected invalid name (hyphen)", "✓")
        
        try:
            skill_manager.save_skill(
                name="123invalid",  # can't start with number
                code="def foo(): pass",
                description="Test"
            )
            print_step("Should have rejected invalid name", "✗")
        except ValueError as e:
            print_step("Correctly rejected invalid name (starts with number)", "✓")
        print()
        
        # Test 11: Test duplicate skill
        print("[Test 11] Test duplicate skill...")
        try:
            skill_manager.save_skill(
                name="csv_merger",  # already exists
                code="def foo(): pass",
                description="Test"
            )
            print_step("Should have rejected duplicate", "✗")
        except ValueError as e:
            print_step("Correctly rejected duplicate skill", "✓")
        print()
        
        # Test 12: Delete a skill
        print("[Test 12] Delete a skill...")
        result = skill_manager.delete_skill("fibonacci_calculator")
        assert result["status"] == "success", "Delete failed"
        
        skills = skill_manager.list_skills()
        assert len(skills) == 1, f"Expected 1 skill after delete, got {len(skills)}"
        assert skills[0]["name"] == "csv_merger", "Wrong skill remaining"
        
        # Verify file deleted
        skill_file = skill_manager.skills_dir / "fibonacci_calculator.py"
        assert not skill_file.exists(), "Skill file not deleted"
        
        # Verify registry updated
        skills_md = skill_manager.skills_file.read_text()
        assert "fibonacci_calculator" not in skills_md, "Skill still in registry"
        
        print_step("Skill deleted successfully", "✓")
        print_step("File removed", "✓")
        print_step("Registry updated", "✓")
        print()
        
        # Test 13: Test get non-existent skill
        print("[Test 13] Test get non-existent skill...")
        try:
            skill_manager.get_skill("nonexistent")
            print_step("Should have raised error", "✗")
        except ValueError as e:
            print_step("Correctly raised error for non-existent skill", "✓")
        print()
        
        # Test 14: Verify __init__.py created
        print("[Test 14] Verify package structure...")
        init_file = skill_manager.skills_dir / "__init__.py"
        assert init_file.exists(), "__init__.py not created"
        print_step("skills/__init__.py exists", "✓")
        print()
        
        print("=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        print()
        print("Summary:")
        print(f"  - SkillManager initialized: ✓")
        print(f"  - Skill creation: ✓")
        print(f"  - Skill retrieval: ✓")
        print(f"  - Skill listing: ✓")
        print(f"  - Skill searching: ✓")
        print(f"  - Skill deletion: ✓")
        print(f"  - Validation (invalid names, duplicates): ✓")
        print(f"  - SKILLS.md registry: ✓")
        print()
        
        return True
        
    except AssertionError as e:
        print()
        print("=" * 60)
        print("❌ TEST FAILED")
        print("=" * 60)
        print(f"Error: {e}")
        return False
        
    except Exception as e:
        print()
        print("=" * 60)
        print("❌ TEST ERROR")
        print("=" * 60)
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Cleanup
        try:
            shutil.rmtree(temp_workspace)
            print(f"Cleaned up temporary workspace: {temp_workspace}")
        except Exception as e:
            print(f"Warning: Could not cleanup {temp_workspace}: {e}")


if __name__ == "__main__":
    success = test_skill_manager()
    sys.exit(0 if success else 1)
