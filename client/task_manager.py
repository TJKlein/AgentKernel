"""Task Manager for async background task execution.

This module provides async middleware capabilities for AgentKernel,
allowing agents to dispatch tasks to background workers and collect
results asynchronously ("fire-and-forget" pattern).
"""

import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Any, Dict, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class TaskManager:
    """Manages background task execution with async orchestration.
    
    This class provides "fire-and-forget" async capabilities similar to
    open-ptc-agent's middleware, but built on top of the synchronous
    AgentHelper execution engine.
    
    Example:
        >>> from agent_kernel import create_agent, TaskManager
        >>> agent = create_agent()
        >>> manager = TaskManager(agent)
        >>> 
        >>> # Dispatch tasks in background
        >>> task1 = manager.dispatch_task("Calculate fibonacci(35)")
        >>> task2 = manager.dispatch_task("Get weather for Paris")
        >>> 
        >>> # Continue working while tasks run...
        >>> 
        >>> # Collect results when ready
        >>> result1 = manager.wait_for_task(task1)
        >>> result2 = manager.wait_for_task(task2)
    """

    def __init__(
        self,
        agent: Any,  # AgentHelper instance
        max_workers: int = 5,
        default_timeout: float = 300.0,
    ):
        """Initialize TaskManager.
        
        Args:
            agent: AgentHelper instance to use for task execution
            max_workers: Maximum number of concurrent background tasks
            default_timeout: Default timeout for task execution (seconds)
        """
        self.agent = agent
        self.max_workers = max_workers
        self.default_timeout = default_timeout
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.tasks: Dict[str, Dict[str, Any]] = {}
        
        logger.info(f"TaskManager initialized with {max_workers} workers")

    def dispatch_task(
        self,
        task_description: str,
        required_tools: Optional[Dict[str, list]] = None,
        verbose: bool = False,
    ) -> str:
        """Dispatch a task to run in the background.
        
        Args:
            task_description: Description of the task to execute
            required_tools: Optional pre-selected tools
            verbose: Whether to print execution progress
            
        Returns:
            task_id: Unique identifier for tracking the task
        """
        task_id = str(uuid.uuid4())[:8]
        
        # Initialize task metadata
        self.tasks[task_id] = {
            "status": "running",
            "description": task_description,
            "result": None,
            "output": None,
            "error": None,
            "started_at": datetime.now().isoformat(),
            "completed_at": None,
            "future": None,
        }
        
        # Submit to background executor
        future = self.executor.submit(
            self._execute_task,
            task_id,
            task_description,
            required_tools,
            verbose,
        )
        
        self.tasks[task_id]["future"] = future
        
        logger.info(f"Dispatched task {task_id}: {task_description[:50]}...")
        return task_id

    def _execute_task(
        self,
        task_id: str,
        task_description: str,
        required_tools: Optional[Dict[str, list]],
        verbose: bool,
    ) -> None:
        """Execute task in background (internal method).
        
        This method runs in a background thread and updates the task
        status in the shared tasks dictionary.
        """
        try:
            # Execute using the agent
            result, output, error = self.agent.execute_task(
                task_description=task_description,
                required_tools=required_tools,
                verbose=verbose,
            )
            
            # Update task status
            self.tasks[task_id].update({
                "status": "completed" if not error else "failed",
                "result": result,
                "output": output,
                "error": error,
                "completed_at": datetime.now().isoformat(),
            })
            
            if error:
                logger.warning(f"Task {task_id} failed with error: {error}")
            else:
                logger.info(f"Task {task_id} completed successfully")
                
        except Exception as e:
            logger.error(f"Task {task_id} raised exception: {e}", exc_info=True)
            self.tasks[task_id].update({
                "status": "failed",
                "error": str(e),
                "completed_at": datetime.now().isoformat(),
            })

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get the current status of a task.
        
        Args:
            task_id: Unique task identifier
            
        Returns:
            Dictionary containing task status and metadata
        """
        task = self.tasks.get(task_id)
        
        if not task:
            return {
                "status": "unknown",
                "error": f"Task {task_id} not found",
            }
        
        # Return a copy without the future object
        status = {k: v for k, v in task.items() if k != "future"}
        return status

    def wait_for_task(
        self,
        task_id: str,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Wait for a task to complete and return results.
        
        This method blocks until the task completes or timeout is reached.
        
        Args:
            task_id: Unique task identifier
            timeout: Maximum time to wait (seconds). Uses default if None.
            
        Returns:
            Dictionary containing task status and results
        """
        task = self.tasks.get(task_id)
        
        if not task:
            return {
                "status": "unknown",
                "error": f"Task {task_id} not found",
            }
        
        future: Optional[Future] = task.get("future")
        if not future:
            return self.get_task_status(task_id)
        
        # Wait for completion
        timeout = timeout or self.default_timeout
        
        try:
            future.result(timeout=timeout)
        except TimeoutError:
            logger.warning(f"Task {task_id} timed out after {timeout}s")
            self.tasks[task_id].update({
                "status": "timeout",
                "error": f"Task exceeded timeout of {timeout}s",
            })
        except Exception as e:
            logger.error(f"Error waiting for task {task_id}: {e}")
        
        return self.get_task_status(task_id)

    def list_tasks(self) -> Dict[str, Dict[str, Any]]:
        """List all tracked tasks.
        
        Returns:
            Dictionary mapping task_ids to their status
        """
        return {
            task_id: {k: v for k, v in task.items() if k != "future"}
            for task_id, task in self.tasks.items()
        }

    def cancel_task(self, task_id: str) -> bool:
        """Attempt to cancel a running task.
        
        Args:
            task_id: Unique task identifier
            
        Returns:
            True if cancellation was successful, False otherwise
        """
        task = self.tasks.get(task_id)
        
        if not task:
            logger.warning(f"Cannot cancel unknown task {task_id}")
            return False
        
        future: Optional[Future] = task.get("future")
        if not future:
            logger.warning(f"Task {task_id} has no future to cancel")
            return False
        
        # Attempt cancellation
        cancelled = future.cancel()
        
        if cancelled:
            self.tasks[task_id].update({
                "status": "cancelled",
                "completed_at": datetime.now().isoformat(),
            })
            logger.info(f"Task {task_id} cancelled")
        
        return cancelled

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the task manager and cleanup resources.
        
        Args:
            wait: Whether to wait for running tasks to complete
        """
        logger.info(f"Shutting down TaskManager (wait={wait})")
        self.executor.shutdown(wait=wait)

    def __del__(self):
        """Cleanup on deletion."""
        try:
            self.shutdown(wait=False)
        except Exception:
            pass
