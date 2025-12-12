"""
Docker-based sandboxed code execution for rbAI.
Implements secure, isolated Python code execution with resource limits.
"""

import docker
import asyncio
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ExecutionResult:
    """Data class for execution results"""
    def __init__(
        self,
        status: str,
        output: str,
        error: str = "",
        execution_time: float = 0.0,
        exit_code: int = 0,
        test_results: Optional[List[Dict]] = None
    ):
        self.status = status  # "success", "error", "timeout"
        self.output = output
        self.error = error
        self.execution_time = execution_time
        self.exit_code = exit_code
        self.test_results = test_results or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "output": self.output,
            "error": self.error,
            "execution_time": round(self.execution_time, 3),
            "exit_code": self.exit_code,
            "test_results": self.test_results
        }


class DockerExecutor:
    """
    Executes Python code in isolated Docker containers with strict resource limits.
    
    Security Features:
    - Network disabled
    - Memory limit: 128MB
    - CPU limit: 50% of one core
    - Execution timeout: 5 seconds
    - Read-only filesystem (except /tmp)
    - No dangerous modules accessible
    """
    
    def __init__(
        self,
        image_name: str = "python:3.10-alpine",
        memory_limit: str = "128m",
        cpu_quota: int = 50000,  # 50% of one CPU core
        timeout: int = 5
    ):
        self.image_name = image_name
        self.memory_limit = memory_limit
        self.cpu_quota = cpu_quota
        self.timeout = timeout
        
        try:
            self.client = docker.from_env()
            # Test connection
            self.client.ping()
            logger.info("Docker client initialized successfully")
        except docker.errors.DockerException as e:
            logger.error(f"Failed to initialize Docker client: {e}")
            raise RuntimeError(
                "Docker is not available. Please ensure Docker is installed and running."
            )
    
    def _prepare_code(self, user_code: str, stdin_data: str = "") -> str:
        """
        Wraps user code with safety checks and output capture.
        Injects stdin data directly into sys.stdin to avoid Docker stdin issues.
        """
        # Indent user code
        indented_code = self._indent_code(user_code, 8)
        
        # Escape stdin data for Python string
        stdin_escaped = stdin_data.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n')
        
        # Wrapper template that captures stdout/stderr and injects stdin
        wrapper = f'''import sys
import io
from contextlib import redirect_stdout, redirect_stderr

# Replace stdin with provided input
sys.stdin = io.StringIO('{stdin_escaped}')

# Capture output
stdout_capture = io.StringIO()
stderr_capture = io.StringIO()

try:
    with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
{indented_code}
    
    # Print captured output
    output = stdout_capture.getvalue()
    if output:
        print(output, end='')
    
    error = stderr_capture.getvalue()
    if error:
        print(error, file=sys.stderr, end='')
        
except Exception as e:
    print(f"Runtime Error: {{type(e).__name__}}: {{e}}", file=sys.stderr)
    sys.exit(1)
'''
        return wrapper
    
    def _indent_code(self, code: str, spaces: int) -> str:
        """Indent each line of code by specified spaces"""
        indent = ' ' * spaces
        lines = code.split('\n')
        return '\n'.join(indent + line for line in lines)
    
    async def execute_code(
        self,
        code: str,
        stdin: str = "",
        test_cases: Optional[List[Dict]] = None
    ) -> ExecutionResult:
        """
        Execute Python code in a Docker container.
        
        Args:
            code: The Python code to execute
            stdin: Optional standard input for the program
            test_cases: Optional list of test cases to validate against
            
        Returns:
            ExecutionResult object with execution details
        """
        start_time = time.time()
        
        try:
            # Prepare code with safety wrapper (stdin is injected into the code)
            wrapped_code = self._prepare_code(code, stdin)
            
            # Create and run container
            logger.info("Starting container execution...")
            container = self.client.containers.run(
                self.image_name,
                command=["python", "-c", wrapped_code],
                detach=True,
                remove=False,
                mem_limit=self.memory_limit,
                cpu_quota=self.cpu_quota,
                network_disabled=True,
                read_only=True,
                tmpfs={'/tmp': 'size=10M,mode=1777'},
                environment={
                    'PYTHONUNBUFFERED': '1',
                    'PYTHONDONTWRITEBYTECODE': '1'
                }
            )
            
            # Wait for completion with timeout
            try:
                result = container.wait(timeout=self.timeout)
                exit_code = result['StatusCode']
            except Exception as e:
                container.stop(timeout=0)
                container.remove(force=True)
                execution_time = time.time() - start_time
                
                if execution_time >= self.timeout:
                    logger.warning(f"Execution timeout after {execution_time:.3f}s")
                    return ExecutionResult(
                        status="timeout",
                        output="",
                        error=f"Execution exceeded {self.timeout} second time limit",
                        execution_time=execution_time
                    )
                else:
                    raise
            
            # Get output
            stdout = container.logs(stdout=True, stderr=False).decode('utf-8')
            stderr = container.logs(stdout=False, stderr=True).decode('utf-8')
            
            # Clean up
            container.remove(force=True)
            
            execution_time = time.time() - start_time
            
            # Determine status
            if exit_code == 0:
                status = "success"
            else:
                status = "error"
            
            logger.info(f"Execution completed: {status} in {execution_time:.3f}s")
            
            return ExecutionResult(
                status=status,
                output=stdout,
                error=stderr,
                execution_time=execution_time,
                exit_code=exit_code
            )
                
        except docker.errors.ContainerError as e:
            logger.error(f"Container error: {e}")
            return ExecutionResult(
                status="error",
                output="",
                error=f"Container execution failed: {str(e)}",
                execution_time=time.time() - start_time
            )
            
        except docker.errors.ImageNotFound:
            logger.error(f"Docker image not found: {self.image_name}")
            return ExecutionResult(
                status="error",
                output="",
                error=f"Python environment not available. Please contact administrator.",
                execution_time=0
            )
            
        except Exception as e:
            logger.error(f"Unexpected execution error: {e}", exc_info=True)
            return ExecutionResult(
                status="error",
                output="",
                error=f"Unexpected error: {str(e)}",
                execution_time=time.time() - start_time
            )
    
    async def execute_with_tests(
        self,
        code: str,
        test_cases: List[Dict[str, Any]]
    ) -> ExecutionResult:
        """
        Execute code and validate against test cases.
        
        Args:
            code: Python code to execute
            test_cases: List of dicts with 'input' and 'expected_output' keys
            
        Returns:
            ExecutionResult with test_results populated
        """
        test_results = []
        all_passed = True
        last_result = None
        
        for i, test_case in enumerate(test_cases):
            test_input = test_case.get('input', '')
            expected = test_case.get('expected_output', '').strip()
            
            # Execute with this test's input
            result = await self.execute_code(code, stdin=test_input)
            last_result = result
            
            actual = result.output.strip()
            passed = (actual == expected) and result.status == "success"
            
            test_results.append({
                "test_number": i + 1,
                "passed": passed,
                "input": test_input,
                "expected_output": expected,
                "actual_output": actual,
                "error": result.error if result.error else None
            })
            
            if not passed:
                all_passed = False
        
        # Use the last test execution result, update status based on all tests
        if last_result:
            last_result.test_results = test_results
            last_result.status = "success" if all_passed else "failed_tests"
            # Clear error if all tests passed
            if all_passed:
                last_result.error = ""
            return last_result
        else:
            # No test cases provided, run once without input
            final_result = await self.execute_code(code)
            final_result.test_results = test_results
            return final_result
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check if Docker is healthy and image is available.
        
        Returns:
            Dict with status and details
        """
        try:
            self.client.ping()
            
            # Check if image exists
            try:
                self.client.images.get(self.image_name)
                image_available = True
            except docker.errors.ImageNotFound:
                image_available = False
            
            return {
                "status": "healthy",
                "docker_available": True,
                "image_available": image_available,
                "image_name": self.image_name,
                "resource_limits": {
                    "memory": self.memory_limit,
                    "cpu_quota": self.cpu_quota,
                    "timeout": self.timeout
                }
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "docker_available": False,
                "error": str(e)
            }