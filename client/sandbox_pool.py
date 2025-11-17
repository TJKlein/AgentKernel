"""Sandbox pool for fast execution with reusable sandboxes."""

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Optional, Any

try:
    import aiohttp
    from microsandbox import PythonSandbox
except ImportError:
    PythonSandbox = None  # type: ignore
    aiohttp = None  # type: ignore

logger = logging.getLogger(__name__)


class SandboxPool:
    """Pool of pre-created sandboxes for fast execution.
    
    This optimization significantly reduces execution time by reusing
    sandboxes instead of creating new ones for each execution.
    
    Can be disabled via config: optimizations.sandbox_pooling = False
    """
    
    def __init__(self, pool_size: int = 3, workspace_dir: str = "./workspace"):
        """Initialize sandbox pool.
        
        Args:
            pool_size: Number of sandboxes to pre-create
            workspace_dir: Workspace directory to mount
        """
        self.pool_size = pool_size
        self.workspace_dir = Path(workspace_dir).resolve()
        self.available: asyncio.Queue = asyncio.Queue()
        self.in_use: set = set()
        self._initialized = False
        self._lock = asyncio.Lock()
        
        logger.info(f"Sandbox pool initialized (size={pool_size}, workspace={workspace_dir})")
    
    async def initialize(self):
        """Pre-create sandboxes in the pool."""
        if self._initialized:
            return
        
        async with self._lock:
            if self._initialized:  # Double-check after acquiring lock
                return
            
            if PythonSandbox is None:
                logger.warning("microsandbox not available, pool will create sandboxes on demand")
                self._initialized = True
                return
            
            logger.info(f"Pre-creating {self.pool_size} sandboxes...")
            tasks = []
            for i in range(self.pool_size):
                tasks.append(self._create_sandbox(f"pool-{i}"))
            
            sandboxes = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, sandbox in enumerate(sandboxes):
                if isinstance(sandbox, Exception):
                    logger.warning(f"Failed to create sandbox {i}: {sandbox}")
                else:
                    await self.available.put(sandbox)
                    logger.debug(f"Added sandbox pool-{i} to pool")
            
            self._initialized = True
            logger.info(f"Sandbox pool ready with {self.available.qsize()} sandboxes")
    
    async def _create_sandbox(self, name: str) -> Any:
        """Create a new sandbox and start it manually (not using context manager).
        
        This allows the sandbox to persist and be reused across multiple executions.
        The sandbox will only be stopped during cleanup().
        """
        if PythonSandbox is None:
            raise ImportError("microsandbox is not installed")
        if aiohttp is None:
            raise ImportError("aiohttp is not installed")
        
        # Instantiate sandbox directly (not using create() context manager)
        sandbox = PythonSandbox(
            name=f"code-execution-{name}-{uuid.uuid4().hex[:8]}"
        )
        
        # Create HTTP session manually
        sandbox._session = aiohttp.ClientSession()
        
        try:
            # Start sandbox with volumes
        await sandbox.start(volumes=[(str(self.workspace_dir), "/workspace")])
            logger.debug(f"Created and started sandbox: {sandbox._name}")
        return sandbox
        except Exception as e:
            # If start fails, close the session and re-raise
            if sandbox._session:
                await sandbox._session.close()
                sandbox._session = None
            logger.error(f"Failed to start sandbox {sandbox._name}: {e}")
            raise
    
    async def acquire(self) -> Any:
        """Get sandbox from pool (or create new if empty).
        
        Returns:
            Sandbox instance ready for execution (already started)
        """
        if not self._initialized:
            await self.initialize()
        
        # Try to get from pool (non-blocking)
        try:
            sandbox = self.available.get_nowait()
            # Verify sandbox is still started and session is valid
            if not sandbox._is_started:
                logger.warning(f"Sandbox {sandbox._name} is not started, recreating...")
                # Recreate this sandbox
                try:
                    if sandbox._session:
                        await sandbox._session.close()
                except Exception:
                    pass
                sandbox = await self._create_sandbox("replacement")
            else:
                # Check if session's event loop is closed (happens when asyncio.run() closes loop)
                try:
                    if sandbox._session and sandbox._session._loop and sandbox._session._loop.is_closed():
                        logger.debug(f"Sandbox {sandbox._name} session loop closed, recreating session...")
                        # Close old session
                        try:
                            await sandbox._session.close()
                        except Exception:
                            pass
            # Create new session in current event loop
                        sandbox._session = aiohttp.ClientSession()
                except (AttributeError, RuntimeError):
                    # Session might not have _loop attribute or loop check failed
                    # Try to recreate session to be safe
                    try:
                        if sandbox._session:
                            await sandbox._session.close()
                    except Exception:
                        pass
                    sandbox._session = aiohttp.ClientSession()
            
            self.in_use.add(sandbox)
            logger.debug(f"Acquired sandbox from pool (available={self.available.qsize()}, in_use={len(self.in_use)})")
            return sandbox
        except asyncio.QueueEmpty:
            # Pool empty, create new sandbox
            logger.info("Pool empty, creating new sandbox on demand")
            sandbox = await self._create_sandbox("dynamic")
            self.in_use.add(sandbox)
            return sandbox
    
    async def release(self, sandbox: Any):
        """Return sandbox to pool (keep it running for reuse).
        
        Args:
            sandbox: Sandbox to return to pool
        """
        if sandbox not in self.in_use:
            logger.warning("Attempting to release sandbox not from pool")
            return
        
        self.in_use.remove(sandbox)
        
        # Verify sandbox is still started before returning to pool
        if not sandbox._is_started:
            logger.warning(f"Sandbox {sandbox._name} is not started, will not return to pool")
            # Clean up the stopped sandbox
            try:
                if sandbox._session:
                    await sandbox._session.close()
            except Exception as e:
                logger.warning(f"Error closing session for stopped sandbox: {e}")
            return
        
        # Optional: Clean sandbox state here (future optimization)
        # await self._clean_sandbox(sandbox)
        
        # Return to pool (sandbox stays running)
        await self.available.put(sandbox)
        logger.debug(f"Returned sandbox to pool (available={self.available.qsize()}, in_use={len(self.in_use)})")
    
    async def _clean_sandbox(self, sandbox: Any):
        """Clean sandbox state between uses (future optimization)."""
        # TODO: Clear Python module cache
        # TODO: Remove temporary files
        # TODO: Reset environment variables
        pass
    
    async def cleanup(self):
        """Cleanup all sandboxes in pool.
        
        Stops all sandboxes and closes their HTTP sessions.
        """
        logger.info("Cleaning up sandbox pool...")
        
        cleaned = 0
        
        # Clean available sandboxes
        while not self.available.empty():
            try:
                sandbox = self.available.get_nowait()
                try:
                    # Stop sandbox first
                    if sandbox._is_started:
                        await sandbox.stop()
                    # Close HTTP session
                    if sandbox._session:
                        await sandbox._session.close()
                        sandbox._session = None
                    cleaned += 1
                except Exception as e:
                    logger.warning(f"Failed to cleanup sandbox {sandbox._name}: {e}")
            except asyncio.QueueEmpty:
                break
        
        # Clean in-use sandboxes
        for sandbox in list(self.in_use):
            try:
                # Stop sandbox first
                if sandbox._is_started:
                    await sandbox.stop()
                # Close HTTP session
                if sandbox._session:
                    await sandbox._session.close()
                    sandbox._session = None
                cleaned += 1
            except Exception as e:
                logger.warning(f"Failed to cleanup sandbox {sandbox._name}: {e}")
        
        self.in_use.clear()
        self._initialized = False
        logger.info(f"Cleaned up {cleaned} sandboxes")


# Global pool instance (singleton pattern)
_global_pool: Optional[SandboxPool] = None
_pool_lock = asyncio.Lock()


async def get_sandbox_pool(pool_size: int = 3, workspace_dir: str = "./workspace") -> SandboxPool:
    """Get or create the global sandbox pool.
    
    Args:
        pool_size: Number of sandboxes in pool
        workspace_dir: Workspace directory to mount
        
    Returns:
        Global sandbox pool instance
    """
    global _global_pool
    
    if _global_pool is not None:
        return _global_pool
    
    async with _pool_lock:
        if _global_pool is not None:  # Double-check
            return _global_pool
        
        _global_pool = SandboxPool(pool_size, workspace_dir)
        await _global_pool.initialize()
        return _global_pool

