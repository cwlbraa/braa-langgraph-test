"""LangGraph test runner agent.

An interactive agent that can clone repositories, run tests, and analyze results.
All tools use the same persistent Docker container.
"""

from __future__ import annotations

import subprocess
from typing import Annotated, Any

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware
from langchain.messages import AnyMessage, HumanMessage
from langchain.tools import tool
from langgraph.runtime import Runtime


# Container management
CONTAINER_NAME = "langgraph-test-runner"
DOCKER_IMAGE = "python:3.11-slim"


def run_in_container(command: str, timeout: int = 300) -> str:
    """Execute a command in the persistent Docker container."""
    try:
        # Check if container exists
        check_cmd = ["docker", "inspect", CONTAINER_NAME]
        result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=5)

        if result.returncode != 0:
            # Container doesn't exist, create it
            create_cmd = [
                "docker", "run", "-d",
                "--name", CONTAINER_NAME,
                "-w", "/tmp",
                DOCKER_IMAGE,
                "tail", "-f", "/dev/null"
            ]
            subprocess.run(create_cmd, check=True, capture_output=True, timeout=30)

        # Execute the command
        exec_cmd = ["docker", "exec", "-w", "/tmp", CONTAINER_NAME, "bash", "-c", command]
        result = subprocess.run(
            exec_cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        # Combine stdout and stderr, include exit code
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += "\n" + result.stderr
        if result.returncode != 0:
            output += f"\nExit code: {result.returncode}"

        return output or "Command executed successfully (no output)"

    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout} seconds"
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def setup_repository() -> str:
    """Clone the langgraph repository and install its dependencies.

    This sets up the environment in a Docker container at /tmp/langgraph.
    The langgraph repo is a monorepo with multiple packages in libs/.
    Idempotent - safe to run multiple times (skips if already set up).
    """
    # Check if already set up
    check_output = run_in_container("test -d /tmp/langgraph/libs/langgraph && echo 'already_exists' || echo 'needs_setup'", timeout=5)

    if "already_exists" in check_output:
        return "Repository already set up at /tmp/langgraph - skipping setup"

    # Install git
    output = run_in_container("apt-get update && apt-get install -y git", timeout=120)

    # Clone repo with --depth 1 for faster clone (large repository)
    clone_output = run_in_container(
        "git clone --depth 1 https://github.com/langchain-ai/langgraph /tmp/langgraph",
        timeout=300  # 5 minutes for clone
    )
    output += "\n" + clone_output

    # Install all langgraph packages from the monorepo
    install_cmds = """
cd /tmp/langgraph && \\
pip install -e libs/langgraph && \\
pip install -e libs/checkpoint && \\
pip install -e libs/checkpoint-sqlite && \\
pip install -e libs/checkpoint-postgres && \\
pip install -e libs/prebuilt && \\
pip install -e libs/sdk-py
"""
    install_output = run_in_container(install_cmds, timeout=400)
    output += "\n" + install_output

    # Install test dependencies
    test_deps = "pytest pytest-cov pytest-dotenv pytest-mock syrupy httpx pytest-xdist pytest-repeat psycopg[binary] pycryptodome redis"
    test_deps_output = run_in_container(f"pip install {test_deps}", timeout=180)
    output += "\n" + test_deps_output

    return output


@tool
def run_tests(test_path: str = "tests/") -> str:
    """Run pytest tests in the langgraph repository.

    Args:
        test_path: Path to tests relative to /tmp/langgraph/libs/langgraph (e.g., "tests/" or "tests/test_pregel.py")

    Returns:
        The test output showing pass/fail results
    """
    output = run_in_container(
        f"cd /tmp/langgraph/libs/langgraph && python -m pytest {test_path} -v",
        timeout=600  # 10 minute timeout for tests
    )

    # Truncate output to avoid exceeding API limits
    # Keep first 5000 chars (setup info) and last 15000 chars (summary)
    if len(output) > 20000:
        output = output[:5000] + f"\n\n... ({len(output) - 20000} chars truncated) ...\n\n" + output[-15000:]

    return output


@tool
def execute_shell(command: str) -> str:
    """Execute a bash command in the Docker container.

    Use this to examine code, run custom commands, or debug issues.
    The repository is at /tmp/langgraph.

    Args:
        command: The bash command to execute
    """
    return run_in_container(command)


class AutoTriggerMiddleware(AgentMiddleware):
    """Middleware that auto-runs setup and triggers test on empty input."""

    def before_agent(self, state: dict[str, Any], runtime: Runtime) -> dict[str, Any] | None:
        """Run setup automatically and inject message to run tests."""
        messages = state.get("messages", [])

        # Auto-trigger on empty input (typical for cron jobs)
        if len(messages) == 0:
            # Run setup (idempotent - skips if already exists)
            print("Running setup_repository automatically...")
            setup_output = setup_repository.invoke({})
            print(f"Setup complete: {setup_output[:100]}...")

            # Inject message to run tests
            return {
                "messages": [
                    HumanMessage(
                        content="The repository is set up. Please run all tests and provide a summary."
                    )
                ]
            }

        return None


# Create agent with custom tools (no ShellToolMiddleware - all tools use same container)
graph = create_agent(
    model="claude-sonnet-4-5-20250929",
    tools=[setup_repository, run_tests, execute_shell],
    system_prompt="""You are a test runner agent for the langgraph repository.

Available tools (all use the same persistent Docker container):
- setup_repository(): Clones repo (depth 1), installs all monorepo packages + test dependencies
- run_tests(test_path="tests/"): Run pytest with optional path filter
- execute_shell(command): Execute any bash command in the container

Workflow:
1. On first run, call setup_repository (this installs everything needed)
2. Then call run_tests() to execute the full test suite
3. Analyze the results and provide a clear summary with:
   - Total tests run
   - Pass/fail counts
   - Key error patterns
   - Specific failing test names if any

For follow-up questions:
- Re-run specific tests: run_tests(test_path="tests/test_pregel.py")
- Examine code: execute_shell(command="cat /tmp/langgraph/libs/langgraph/langgraph/pregel/main.py")
- Debug failures interactively

The langgraph repo is a monorepo at /tmp/langgraph with packages in libs/.""",
    middleware=[
        AutoTriggerMiddleware(),  # Auto-trigger on empty input
    ],
)
