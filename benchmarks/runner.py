"""Benchmark execution harness."""

import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Any

from config.loader import load_config
from config.schema import ExecutionConfig
from client.base import ExecutionResult
from client.filesystem_helpers import FilesystemHelper
from client.opensandbox_executor import OpenSandboxExecutor

from .tasks.schema import Task, TaskResult
from .validators import Validator

logger = logging.getLogger(__name__)

# Tool API description for PTC tasks that use mock_mcp_client (so the LLM knows what to call).
MOCK_MCP_TOOLS_DESCRIPTION = """Use this API only: from mock_mcp_client import call_mcp_tool.
Call as: call_mcp_tool(server_name, method_name, args_dict).

Available tools:
- calculator: add/subtract/multiply/divide/power/sqrt/calculate/sum_list/avg_list
- weather: get_weather/get_forecast/get_historical/compare_locations (location, units)
- filesystem: read_file/write_file/append_file/list_directory/file_exists/get_size/count_lines/read_lines (path)
- database: query (table, columns, where)/aggregate (table, type, column)/join (table, join_table, on)
- http: get/post/put/delete/fetch_json (url, data)
- text: split/join/search/replace/regex_match/regex_findall/to_upper/to_lower/strip/word_count (text)
- email: send/fetch/search (to, subject, body)
- calendar: create_event/list_events/delete_event/count_events (title, date)
- math: fibonacci/factorial/gcd/lcm/is_prime/primes_up_to (n)
- transform: sort_by/filter/map_field/group_by/sum_field/count_by/unique_values (data, key)

Always use call_mcp_tool with exactly these tool and method names."""


def _task_uses_mock_mcp_client(task: "Task") -> bool:
    """True if this task's setup uses mock_mcp_client (PTC benchmark style)."""
    for file_def in getattr(task, "setup_files", []) or []:
        if "mock_mcp_client" in file_def.get("source", ""):
            return True
    return False


def categorize_failure(error_str: Optional[str], output_str: str = "", validation_details: Optional[Dict] = None) -> Optional[str]:
    """Categorize the type of failure for analysis.
    
    Returns one of:
    - TIMEOUT: Execution exceeded time limit
    - IMPORT_ERROR: Missing dependency or import failure
    - SYNTAX_ERROR: Invalid Python syntax in generated code
    - RUNTIME_ERROR: Exception during execution
    - OUTPUT_MISMATCH: Output doesn't match expected format
    - SANDBOX_VIOLATION: Attempted restricted operation
    - VALIDATION_FAILED: Generic validation failure
    - UNKNOWN: Could not determine failure type
    - None: No failure (success)
    """
    if not error_str:
        # Check validation details
        if validation_details and validation_details.get("error"):
            error_str = validation_details.get("error")
        else:
            return None
    
    error_lower = error_str.lower()
    
    # Timeout detection
    if "timeout" in error_lower or "time limit" in error_lower:
        return "TIMEOUT"
    
    # Import error detection
    if "import" in error_lower or "modulenotfound" in error_lower or "no module named" in error_lower:
        return "IMPORT_ERROR"
    
    # Syntax error detection
    if "syntax" in error_lower or "indentation" in error_lower or "parse error" in error_lower:
        return "SYNTAX_ERROR"
    
    # Sandbox violation detection
    if "sandbox" in error_lower or "permission" in error_lower or "access denied" in error_lower or "not allowed" in error_lower:
        return "SANDBOX_VIOLATION"
    
    # Runtime error detection (general Python exceptions)
    if any(exc in error_lower for exc in ["exception", "traceback", "error:", "raise ", "assertion"]):
        return "RUNTIME_ERROR"
    
    # Output mismatch detection
    if validation_details:
        if "expected" in str(validation_details).lower() or "actual" in str(validation_details).lower():
            return "OUTPUT_MISMATCH"
        if validation_details.get("score") is not None and validation_details.get("score") < 1.0:
            return "VALIDATION_FAILED"
    
    # Check output for validation patterns
    if output_str and validation_details and not validation_details.get("success", True):
        return "VALIDATION_FAILED"
    
    return "UNKNOWN"


class BenchmarkRunner:
    """Runs benchmark tasks across configured backends with dual approach support (PTC vs FC)."""

    def __init__(
        self,
        backend: str,
        n_runs: int = 5,
        cold_start: bool = True,
        llm_config=None,
        use_rlm: bool = False,
        approach: str = "both",  # "ptc", "function_calling", or "both"
    ):
        """Initialize runner.

        Args:
            backend: Sandbox backend ("opensandbox", "subprocess")
            n_runs: Number of times to run each task (for statistical variance)
            cold_start: Whether to create a fresh sandbox for each run
            llm_config: Optional LLM configuration for agentic evaluation
            use_rlm: If True, run RLM (Recursive Language Model) path for tasks with context_data_source
            approach: Which approach to run: "ptc", "function_calling", or "both"
        """
        self.backend = backend.lower()
        self.n_runs = n_runs
        self.cold_start = cold_start
        self.use_rlm = use_rlm
        self.approach = approach
        self.config = load_config(Path(__file__).parent.parent / "config.yaml")
        self.llm_config = llm_config
        
        # Setup helpers (keeping this as it's used elsewhere)
        self.fs_helper = FilesystemHelper(
            workspace_dir=self.config.execution.workspace_dir,
            servers_dir=self.config.execution.servers_dir,
            skills_dir=self.config.execution.skills_dir,
        )
        
        # We don't instantiate the executor here if cold_start=True
        # We'll instantiate it per task/run
        self._shared_executor = None
        if not self.cold_start:
            self._shared_executor = self._create_executor()
            
        # Initialize CodeGenerator if running dynamic evaluation
        self.code_generator = None
        if self.llm_config and self.llm_config.enabled:
            from client.code_generator import CodeGenerator
            self.code_generator = CodeGenerator(llm_config=self.llm_config, tool_descriptions={})
        
        # Initialize FC runner if needed
        self.fc_runner = None
        if self.approach in ("function_calling", "both"):
            from benchmarks.function_calling_runner import FunctionCallingRunner
            self.fc_runner = FunctionCallingRunner(llm_config=self.llm_config)

    def _create_executor(self):
        """Create a fresh executor instance."""
        if self.backend == "subprocess":
            from benchmarks.baselines import SubprocessBaseline
            executor = SubprocessBaseline(execution_config=self.config.execution, guardrail_config=self.config.guardrails, optimization_config=self.config.optimizations)
        else:
            executor = OpenSandboxExecutor(
                execution_config=self.config.execution,
                guardrail_config=self.config.guardrails,
                optimization_config=self.config.optimizations,
            )
        return executor
        
    def load_tasks(
        self, 
        categories: Optional[List[str]] = None, 
        difficulties: Optional[List[str]] = None,
        tags: Optional[List[str]] = None
    ) -> List[Task]:
        """Load tasks from JSON definition files."""
        tasks = []
        tasks_dir = Path(__file__).parent / "tasks"
        
        for category_dir in tasks_dir.iterdir():
            if not category_dir.is_dir() or category_dir.name.startswith("__"):
                continue
                
            if categories and category_dir.name not in categories:
                continue
                
            tasks_file = category_dir / "tasks.json"
            if not tasks_file.exists():
                continue
                
            try:
                with open(tasks_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        # Add category if missing
                        if "category" not in item:
                            item["category"] = category_dir.name
                            
                        task = Task.from_dict(item)
                        
                        # Filter by difficulty
                        if difficulties and task.difficulty not in difficulties:
                            continue
                            
                        # Filter by tags
                        if tags and not any(tag in task.tags for tag in tags):
                            continue
                            
                        tasks.append(task)
            except Exception as e:
                logger.error(f"Failed to parse {tasks_file}: {e}")
                
        return sorted(tasks, key=lambda t: (t.category, t.difficulty, t.id))

    def _benchmark_project_root(self) -> Path:
        """Project root for benchmark (same resolution as executor when run from repo)."""
        root = Path(__file__).resolve().parent.parent
        # Match executor: workspace is relative to project root
        return root

    def _get_context_data_path(self, task: Task) -> Optional[Path]:
        """Return path to context data fixture for RLM tasks, or None."""
        if not getattr(task, "context_data_source", None):
            return None
        tasks_dir = Path(__file__).parent / "tasks"
        fixture_path = tasks_dir / task.category / "fixtures" / task.context_data_source
        return fixture_path if fixture_path.exists() else None

    def _load_context_data(self, task: Task) -> Optional[str]:
        """Load context data for RLM tasks from task's context_data_source fixture."""
        path = self._get_context_data_path(task)
        if path is None:
            return None
        try:
            return path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to read RLM context {path}: {e}")
            return None

    def _run_task_rlm(self, task: Task, executor, overall_start_time: float) -> TaskResult:
        """Run a single RLM task via RecursiveAgent (LLM generates code using CONTEXT_DATA and ask_llm)."""
        from client.recursive_agent import RecursiveAgent

        context_path = self._get_context_data_path(task)
        if context_path is None:
            return TaskResult(
                task_id=task.id, task_name=task.name, category=task.category, difficulty=task.difficulty,
                success=False, score=0.0, execution_time=0.0, output="", error="RLM context fixture not found",
                validation={}, backend=self.backend, timestamp=time.time(), skipped=False,
                approach="ptc", failure_type="IMPORT_ERROR"
            )

        fs_helper = self.fs_helper
        agent = RecursiveAgent(
            fs_helper=fs_helper,
            executor=executor,
            optimization_config=self.config.optimizations,
            llm_config=self.llm_config,
        )
        if self.code_generator and getattr(self.code_generator, "_llm_client", None):
            agent.code_generator._llm_client = self.code_generator._llm_client
            agent.code_generator._model_name = getattr(self.code_generator, "_model_name", None) or (self.llm_config.model if self.llm_config else None)

        result, output_str, error_str = agent.execute_recursive_task(
            task_description=task.prompt,
            context_data=context_path,
            verbose=False,
        )
        total_tts = time.time() - overall_start_time
        output_str = str(output_str or "")
        error_str = str(error_str) if error_str else None

        if result == ExecutionResult.SUCCESS:
            passed, score, details = Validator.validate(task, output_str)
        else:
            passed, score, details = False, 0.0, {"error": error_str or str(result)}

        failure_type = categorize_failure(error_str, output_str, details) if not passed else None
        return TaskResult(
            task_id=task.id,
            task_name=task.name,
            category=task.category,
            difficulty=task.difficulty,
            success=passed,
            score=score,
            execution_time=total_tts,
            output=output_str,
            error=error_str,
            validation=details,
            backend=self.backend,
            timestamp=time.time(),
            skipped=False,
            approach="ptc",
            iterations=1,
            total_time=total_tts,
            llm_generation_time=0.0,
            final_error=error_str if not passed else None,
            failure_type=failure_type
        )

    def setup_workspace(self, task: Task) -> None:
        """Create setup files in the workspace directory."""
        # Resolve workspace relative to project root so it matches executor (opensandbox)
        root = self._benchmark_project_root()
        workspace = (root / self.config.execution.workspace_dir.lstrip("./")).resolve()
        
        # Clean existing workspace task files only - preserve executor directories (client, servers, skills)
        # The executor writes these files; we should not delete them between tasks
        if workspace.exists() and workspace.is_dir():
            for item in workspace.iterdir():
                # Skip hidden dirs, .mcp, .replay, and executor-required directories
                if item.name in [".mcp", ".replay", "client", "servers", "skills"] or item.name.startswith("."):
                    continue
                # Also skip directories that might be volume mounts
                if item.is_dir() and item.name in ["data", "output", "logs", "temp", "tmp"]:
                    continue
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    import shutil
                    shutil.rmtree(item)
        
        # Create setup files
        for file_def in task.setup_files:
            if "path" not in file_def or ("content" not in file_def and "source" not in file_def):
                continue
                
            path = file_def["path"]
            # Ensure safe path within workspace
            safe_path = (workspace / path.lstrip("/")).resolve()
            if not str(safe_path).startswith(str(workspace)):
                logger.error(f"Skipping unsafe setup path: {path}")
                continue
                
            safe_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Use provided content or copy from source fixture / absolute path
            if "content" in file_def:
                safe_path.write_text(file_def["content"], encoding="utf-8")
            elif "source" in file_def:
                import shutil
                source_raw = file_def["source"]
                source_path = Path(source_raw)
                if source_path.is_absolute() and source_path.exists():
                    shutil.copy2(source_path, safe_path)
                else:
                    fixture_path = Path(__file__).parent / "tasks" / task.category / "fixtures" / source_raw
                    if fixture_path.exists():
                        shutil.copy2(fixture_path, safe_path)
                    else:
                        logger.error(f"Fixture not found: {fixture_path}")

    def run_task(self, task: Task) -> TaskResult:
        """Execute a single task with full agent loop: LLM generates code, runtime executes, validator checks.
        
        If self.n_runs > 1, this represents a single run of the task.
        The wrapper `run_suite` handles aggregating multiple runs.
        """
        if self.backend not in task.supported_backends:
            return TaskResult(
                task_id=task.id,
                task_name=task.name,
                category=task.category,
                difficulty=task.difficulty,
                success=False,
                score=0.0,
                execution_time=0.0,
                output="",
                error=None,
                validation={},
                backend=self.backend,
                timestamp=time.time(),
                skipped=True,
                skip_reason=f"Backend '{self.backend}' not in supported backends {task.supported_backends}",
                approach="ptc",
            )

        # Same tasks run with or without recursive: RLM tasks get CONTEXT_DATA in both modes;
        # with --recursive they also get ask_llm (RecursiveAgent path).
        has_rlm_context = getattr(task, "context_data_source", None) is not None

        try:
            self.setup_workspace(task)

            # Setup executor
            executor = self._create_executor() if self.cold_start else self._shared_executor

            # Override guardrail max_execution_time for this task
            if hasattr(executor, 'guardrail_config') and executor.guardrail_config is not None:
                executor.guardrail_config.max_execution_time = task.timeout + 2

            # --- RLM path: RecursiveAgent with context_data (LLM + use_rlm) ---
            if has_rlm_context and self.use_rlm and self.code_generator and task.prompt:
                return self._run_task_rlm(task, executor, overall_start_time=time.time())

            # --- RLM baseline: run reference code with injected CONTEXT_DATA ---
            if has_rlm_context and not self.code_generator:
                context_content = self._load_context_data(task)
                if context_content is None:
                    return TaskResult(
                        task_id=task.id, task_name=task.name, category=task.category, difficulty=task.difficulty,
                        success=False, score=0.0, execution_time=0.0, output="", error="RLM context fixture not found",
                        validation={}, backend=self.backend, timestamp=time.time(), skipped=False,
                        approach="ptc", failure_type="IMPORT_ERROR"
                    )
                exec_start = time.time()
                result, output_str, error_str = executor.execute(
                    task.reference_code,
                    context={"inputs": {"CONTEXT_DATA": context_content}},
                )
                exec_time_total = time.time() - exec_start
                output_str = str(output_str or "")
                error_str = str(error_str) if error_str else None
                if result == ExecutionResult.SUCCESS:
                    passed, score, details = Validator.validate(task, output_str)
                else:
                    passed, score, details = False, 0.0, {"error": str(result)}
                failure_type = categorize_failure(error_str, output_str, details) if not passed else None
                return TaskResult(
                    task_id=task.id, task_name=task.name, category=task.category, difficulty=task.difficulty,
                    success=passed, score=score, execution_time=exec_time_total, output=output_str, error=error_str,
                    validation=details, backend=self.backend, timestamp=time.time(), skipped=False,
                    approach="ptc",
                    iterations=1, total_time=exec_time_total, llm_generation_time=0.0, final_error=error_str if not passed else None,
                    failure_type=failure_type
                )

            # Agent Loop: Generation -> Execution -> Validation
            overall_start_time = time.time()
            llm_gen_time_total = 0.0
            exec_time_total = 0.0

            iteration = 0
            # Use LLM retries if generator available, otherwise single shot with reference code
            max_iterations = task.max_retries if self.code_generator and task.prompt else 1
            passed = False
            score = 0.0
            details = {}
            output_str = ""
            error_str = None
            code_to_run = None  # Last code executed (for skill extraction / TaskResult.generated_code)

            # Context for LLM retries
            previous_errors = []
            any_llm_used = False

            while iteration < max_iterations and not passed:
                iteration += 1

                # 1. Generation Phase (Agent generates code)
                if self.code_generator and task.prompt:
                    # Special dataset tasks need direct prompt (no full script wrapper)
                    obj_fn = getattr(task, "objective_fn_name", None)
                    if obj_fn in ("ds1000_execution", "bigcode_execution", "humaneval_execution", "spider_sql"):
                        prompt = task.prompt  # Already has task-specific format
                    else:
                        prompt = f"Write a Python script to solve this task:\n\n{task.prompt}\n\nYour script should print output that can be validated."
                    if previous_errors:
                        prompt += f"\n\nPrevious attempts failed. Fix these errors:\n"
                        for i, prev_err in enumerate(previous_errors):
                            prompt += f"\nAttempt {i+1}:\n```\n{prev_err}\n```\n"
                    
                    use_mock = _task_uses_mock_mcp_client(task)
                    llm_start = time.time()
                    try:
                        code_to_run, used_llm = self.code_generator.generate_complete_code(
                            required_tools={},
                            task_description=prompt,
                            task_specific_calls="",
                            header_comment="# MRBS Agent Task",
                            skill_listing="",
                            use_mock_mcp_client=use_mock,
                            mock_tools_description=MOCK_MCP_TOOLS_DESCRIPTION if use_mock else None,
                        )
                        if not code_to_run or code_to_run.strip() == "":
                            raise ValueError("LLM returned empty code")
                        # If fallback produced no executable code (only comments), use reference for meaningful result
                        if "# No usage code generated" in code_to_run and task.reference_code:
                            code_to_run = task.reference_code
                            used_llm = False
                            logger.info("Using reference code (LLM fallback had no executable code)")
                    except Exception as e:
                        logger.error(f"LLM Generation failed: {e}")
                        error_str = f"LLM Generation failed: {e}"
                        break
                    any_llm_used = any_llm_used or used_llm
                    if used_llm:
                        llm_gen_time_total += (time.time() - llm_start)
                else:
                    # Fallback to reference code for baseline comparison
                    code_to_run = task.reference_code
                    used_llm = False
                    if not code_to_run:
                        error_str = "No prompt for LLM generation and no reference code available."
                        break
                
                # 2. Execution Phase (inject CONTEXT_DATA for RLM tasks so same tasks run with/without --recursive)
                exec_start = time.time()
                exec_context = None
                if has_rlm_context:
                    context_content = self._load_context_data(task)
                    if context_content is not None:
                        exec_context = {"inputs": {"CONTEXT_DATA": context_content}}
                result, output, error = executor.execute(code_to_run, context=exec_context)
                exec_time_total += (time.time() - exec_start)
                
                output_str = str(output) if output is not None else ""
                error_str = str(error) if error is not None else None
                
                # 3. Validation Phase
                if result == ExecutionResult.SUCCESS:
                    passed, score, details = Validator.validate(task, output_str)
                    if score < task.min_score:
                        passed = False
                        if not error_str:
                            error_str = "Validation failed: output did not meet minimum score requirements."
                            if details.get("error"):
                                error_str += f" Reason: {details['error']}"
                else:
                    passed = False
                    score = 0.0
                    details = {"error": f"Execution failed with status: {result}"}
                    if not error_str:
                        error_str = f"Sandbox Exception: {result.name}"
                
                # Setup feedback for next iteration if failed
                if not passed:
                    feedback = ""
                    if error_str:
                        feedback += f"Runtime Error:\n{error_str}\n"
                    if output_str:
                        feedback += f"Runtime Output:\n{output_str}\n"
                    feedback += f"Validation State: {details}"
                    previous_errors.append(feedback)
            
            overall_end_time = time.time()
            total_tts = overall_end_time - overall_start_time
            
            # Cleanup executor if we created a fresh one
            if self.cold_start and hasattr(executor, "close"):
                pass
                
            failure_type = categorize_failure(error_str, output_str, details) if not passed else None
            return TaskResult(
                task_id=task.id,
                task_name=task.name,
                category=task.category,
                difficulty=task.difficulty,
                success=passed,
                score=score,
                execution_time=exec_time_total, # Only the substrate time
                output=output_str,
                error=error_str,
                validation=details,
                backend=self.backend,
                timestamp=time.time(),
                skipped=False,
                approach="ptc",  # Mark as PTC approach
                
                # Agentic stats
                iterations=iteration,
                total_time=total_tts,
                llm_generation_time=llm_gen_time_total,
                final_error=error_str if not passed else None,
                failure_type=failure_type,
                used_llm=any_llm_used,
                generated_code=code_to_run,
            )
            
        except BaseException as e:
            # Catch BaseException to handle pyo3 Rust panics and other critical errors
            logger.error(f"Task {task.id} failed catastrophically: {e}")
            return TaskResult(
                task_id=task.id,
                task_name=task.name,
                category=task.category,
                difficulty=task.difficulty,
                success=False,
                score=0.0,
                execution_time=0.0,
                output="",
                error=str(e),
                validation={"error": "Harness exception"},
                backend=self.backend,
                timestamp=time.time(),
                skipped=False,
                approach="ptc",
                iterations=1,
                total_time=0.0,
                llm_generation_time=0.0,
                final_error=str(e),
                failure_type="RUNTIME_ERROR"
            )


    def run_task_fc(self, task: Task) -> TaskResult:
        """Execute a single task using Function Calling (FC) approach.
        
        This runs the traditional tool-calling loop where the LLM emits JSON
tool calls and the framework executes them.
        """
        if not self.fc_runner:
            return TaskResult(
                task_id=task.id,
                task_name=task.name,
                category=task.category,
                difficulty=task.difficulty,
                success=False,
                score=0.0,
                execution_time=0.0,
                output="",
                error="FC runner not initialized",
                validation={},
                backend=self.backend,
                timestamp=time.time(),
                skipped=True,
                skip_reason="FC runner not initialized",
                approach="function_calling",
                failure_type=None
            )
        
        # Run task via FC runner
        fc_result = self.fc_runner.run_task(task)
        
        # Validate the output
        output_str = fc_result.get("output", "")
        if fc_result.get("success"):
            passed, score, details = Validator.validate(task, output_str)
        else:
            passed, score, details = False, 0.0, {"error": fc_result.get("error", "Unknown error")}
        
        failure_type = categorize_failure(fc_result.get("error"), output_str, details) if not passed else None
        return TaskResult(
            task_id=task.id,
            task_name=task.name,
            category=task.category,
            difficulty=task.difficulty,
            success=passed,
            score=score,
            execution_time=fc_result.get("execution_time", 0.0),
            output=output_str,
            error=fc_result.get("error"),
            validation=details,
            backend=self.backend,
            timestamp=time.time(),
            skipped=False,
            approach="function_calling",
            # FC-specific metrics
            llm_calls=fc_result.get("llm_calls", 0),
            tool_calls=fc_result.get("tool_calls", 0),
            retries=fc_result.get("retries", 0),
            cost=fc_result.get("cost", 0.0),
            failure_type=failure_type
        )

    def run_suite(self, tasks: List[Task]) -> List[TaskResult]:
        """Run a suite of tasks, possibly multiple times, with dual approach support."""
        all_results = []
        
        try:
            from tqdm import tqdm
            has_tqdm = True
        except ImportError:
            has_tqdm = False
        
        # Determine approaches to run for each task
        def should_run_approach(task, approach):
            """Check if a task supports a given approach."""
            if approach == "ptc":
                return True  # All tasks support PTC by default
            elif approach == "function_calling":
                # FC is supported if task has function_calling in approaches
                # or has PTC-style tasks that we can adapt
                if hasattr(task, 'approaches') and task.approaches:
                    return "function_calling" in task.approaches
                # Default: FC supported for tasks with mock_mcp_client setup
                for file_def in task.setup_files:
                    if 'mock_mcp_client' in file_def.get('source', ''):
                        return True
                return False
            return False
        
        # Build list of (task, approach) tuples to run
        runs = []
        for task in tasks:
            if self.approach in ("ptc", "both") and should_run_approach(task, "ptc"):
                for _ in range(self.n_runs):
                    runs.append((task, "ptc"))
            if self.approach in ("function_calling", "both") and should_run_approach(task, "function_calling"):
                for _ in range(self.n_runs):
                    runs.append((task, "function_calling"))
        
        total_runs = len(runs)
        iterator = range(total_runs)
        if has_tqdm:
            iterator = tqdm(iterator, desc=f"Running on {self.backend} ({self.approach})")
        
        for idx in iterator:
            task, approach = runs[idx]
            
            if approach == "ptc":
                res = self.run_task(task)
            else:  # function_calling
                res = self.run_task_fc(task)
            
            all_results.append(res)
            
            if not has_tqdm:
                print(f"[{idx+1}/{total_runs}] {task.id} ({approach}): "
                      f"{'Skipped' if res.skipped else 'Pass' if res.success else 'Fail'} "
                      f"({res.execution_time:.2f}s)")
        
        return all_results
