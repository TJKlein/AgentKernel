"""Data schemas for the benchmark suite."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


@dataclass
class PTCApproach:
    """PTC (Programmatic Tool Calling) approach configuration."""
    agent_generates: str = "Python code importing tools"
    execution: str = "Code runs in sandbox"
    prompt: Optional[str] = None  # Override task-level prompt for PTC
    reference_code: Optional[str] = None  # Override task-level reference_code for PTC


@dataclass
class FCApproach:
    """FC (Function Calling) approach configuration."""
    agent_generates: str = "JSON function calls"
    execution: str = "Framework calls tools, results fed back to LLM"
    prompt: Optional[str] = None  # Override task-level prompt for FC
    tools: List[Dict[str, Any]] = field(default_factory=list)  # Tool schemas for FC
    max_steps: int = 10  # Max LLM-tool interaction steps


@dataclass
class Task:
    """A benchmark task definition with dual approach support (PTC vs FC)."""
    
    # Fields without Defaults (must come first in dataclasses)
    id: str
    difficulty: str
    name: str
    description: str
    validation_type: str
    
    # Fields with Defaults
    category: str = "uncategorized"
    reference_code: str = ""  # Default reference implementation
    expected_output: Optional[str] = None
    custom_validator: Optional[str] = None
    
    # Dynamic LLM Evaluation Fields (Agent Loop)
    prompt: Optional[str] = None  # Default prompt (used if approaches not set)
    max_retries: int = 3
    
    setup_files: List[Dict[str, str]] = field(default_factory=list)
    supported_backends: List[str] = field(default_factory=list)
    timeout: int = 30
    tags: List[str] = field(default_factory=list)
    min_score: float = 1.0
    # RLM (Recursive Language Model): path to fixture file for CONTEXT_DATA (relative to category fixtures/)
    context_data_source: Optional[str] = None
    
    # NEW: Dual approach support for PTC vs FC comparison
    approaches: Optional[Dict[str, Union[PTCApproach, FCApproach, Dict]]] = None
    # Structure: {"ptc": PTCApproach, "function_calling": FCApproach}
    # If not provided, task uses default PTC mode with task-level prompt/reference_code

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """Create a Task from a dictionary."""
        # Parse approaches if present
        approaches_data = data.get("approaches")
        approaches = None
        if approaches_data:
            approaches = {}
            if "ptc" in approaches_data:
                ptc_data = approaches_data["ptc"]
                if isinstance(ptc_data, dict):
                    approaches["ptc"] = PTCApproach(**ptc_data)
                else:
                    approaches["ptc"] = ptc_data
            if "function_calling" in approaches_data:
                fc_data = approaches_data["function_calling"]
                if isinstance(fc_data, dict):
                    approaches["function_calling"] = FCApproach(**fc_data)
                else:
                    approaches["function_calling"] = fc_data
        
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            difficulty=data.get("difficulty", "medium"),
            tags=data.get("tags", []),
            timeout=data.get("timeout", 10),
            supported_backends=data.get("supported_backends", ["opensandbox", "microsandbox", "monty"]),
            min_score=data.get("min_score", 1.0),
            expected_output=data.get("expected_output", None),
            custom_validator=data.get("custom_validator", None),
            validation_type=data.get("validation_type", "exact"),
            category=data.get("category", "uncategorized"),
            reference_code=data.get("reference_code", ""),
            prompt=data.get("prompt", None),
            max_retries=data.get("max_retries", 3),
            setup_files=data.get("setup_files", []),
            context_data_source=data.get("context_data_source", None),
            approaches=approaches,
        )


@dataclass
class TaskResult:
    """Result of a single benchmark task execution."""
    task_id: str
    task_name: str
    category: str
    difficulty: str
    success: bool
    score: float
    execution_time: float     # Substrate runtime ONLY
    output: str
    error: Optional[str]
    validation: Dict[str, Any]
    backend: str
    timestamp: float
    skipped: bool = False
    skip_reason: Optional[str] = None
    
    # NEW: Approach identifier (PTC vs FC)
    approach: str = "ptc"  # "ptc" or "function_calling"
    
    # Agentic Evaluation Metrics
    iterations: int = 1
    total_time: float = 0.0   # TTS (Time-To-Success including LLM latency)
    llm_generation_time: float = 0.0
    final_error: Optional[str] = None
    
    # NEW: FC-specific metrics
    llm_calls: int = 0        # Number of LLM calls (FC mode)
    tool_calls: int = 0       # Number of tool calls made (FC mode)
    retries: int = 0          # Tool call retries / error recovery attempts
    cost: float = 0.0         # Estimated cost in USD


@dataclass
class BenchmarkMetrics:
    """Aggregate metrics for a benchmark run."""
    
    # Overall
    total_tasks: int
    attempted_tasks: int
    passed_tasks: int
    failed_tasks: int
    skipped_tasks: int
    pass_rate: float
    avg_score: float
    
    # Performance
    avg_execution_time: float
    median_execution_time: float
    p95_execution_time: float
    total_wall_time: float
    
    # Reliability
    timeout_count: int
    error_count: int
    
    # Breakdowns
    category_breakdown: Dict[str, Dict[str, Any]]
    difficulty_breakdown: Dict[str, Dict[str, Any]]
    
    # NEW: Approach breakdown (PTC vs FC comparison)
    approach_breakdown: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # Structure: {"ptc": {...}, "function_calling": {...}}
    # Each with: pass_rate, avg_time, avg_cost, avg_retries, etc.
    
    # Agentic Evaluation Metrics
    avg_iterations: float = 1.0
    avg_time_to_success: float = 0.0 # Total time including LLM
    avg_llm_generation_time: float = 0.0
    
    # NEW: FC and cost metrics
    avg_llm_calls: float = 0.0      # Average LLM calls per task (FC mode)
    avg_tool_calls: float = 0.0     # Average tool calls per task (FC mode)
    avg_retries: float = 0.0        # Average retries per task
    total_cost: float = 0.0         # Total estimated cost
    avg_cost: float = 0.0           # Average cost per task
