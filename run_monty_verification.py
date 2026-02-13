import subprocess
import sys
import os

def run_example(script_name, env_vars=None):
    print(f"\nExample: {script_name}")
    print("=" * 60)
    
    cmd = [sys.executable, script_name]
    env = os.environ.copy()
    if env_vars:
        env.update(env_vars)
        for k, v in env_vars.items():
            print(f"ENV: {k}={v}")
            
    try:
        result = subprocess.run(
            cmd, 
            cwd=os.path.dirname(os.path.abspath(__file__)),
            env=env,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("Usage: SUCCESS")
            print(result.stdout[-500:]) # Last 500 chars
        else:
            print("Usage: FAILED")
            print("Stdout:")
            print(result.stdout)
            print("Stderr:")
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"Exception: {e}")
        return False
        
    return True

def main():
    print("Running Monty/RLM Verification Suite")
    
    # RLM Examples (require Monty implicitly or explicitly)
    rlm_scripts = [
        "examples/15_recursive_agent.py",
        "examples/16_recursive_agent_with_tools.py"
    ]
    
    # Standard Examples running on Monty
    monty_standard_scripts = [
        "examples/00_simple_api.py",
        # "examples/13_programmatic_tools.py" # Verify if compatible with Monty
    ]
    
    success_count = 0
    total_count = len(rlm_scripts) + len(monty_standard_scripts)
    
    print(f"\nRunning {total_count} tests...")
    
    # 1. RLM Examples
    for script in rlm_scripts:
        if run_example(script):
            success_count += 1
            
    # 2. Standard Examples with SANDBOX_TYPE=monty
    for script in monty_standard_scripts:
        if run_example(script, {"SANDBOX_TYPE": "monty"}):
            success_count += 1
            
    print(f"\nSummary: {success_count}/{total_count} passed.")
    if success_count == total_count:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
