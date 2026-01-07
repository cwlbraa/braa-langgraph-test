# LangGraph Test Runner Agent

An interactive agent that clones the LangGraph repository, runs tests, and analyzes results. Uses Docker for full git and network access with persistent containers.

## Prerequisites

- **Docker** must be installed and running
- **Anthropic API key** in your environment

## Quick Start

1. Install dependencies with [uv](https://github.com/astral-sh/uv):
   ```bash
   uv sync
   ```

2. Ensure your Anthropic API key is in `.env`:
   ```bash
   ANTHROPIC_API_KEY=sk-ant-...
   ```

3. **Test locally** (easiest):
   ```bash
   python test_agent.py
   ```

   This runs the agent directly and shows results in your terminal. The agent will:
   - Create a Docker container
   - Clone langgraph repository
   - Install dependencies
   - Run all tests
   - Show Claude's analysis

4. **Or use LangGraph Studio**:
   ```bash
   langgraph dev
   ```

   Then send any message in Studio.

## How It Works

The agent uses `create_agent` with three custom tools that all share one persistent Docker container:

**Tools:**
1. `setup_repository()` - Clone langgraph repo and install dependencies
2. `run_tests(test_path)` - Run pytest with optional path filter
3. `execute_shell(command)` - Execute any bash command

**Auto-Trigger:**
- On first run (empty input), agent automatically calls setup_repository then run_tests
- LLM analyzes results and provides summary
- Follow-ups can re-run specific tests or explore code

**Container:**
- All tools use the same persistent container (`langgraph-test-runner`)
- Repository and installed packages persist across tool calls
- LLM has full access to examine files, re-run tests, debug

## What Works

**Full Capabilities** ✅
- Clone any GitHub repository
- Install Python packages (pip, uv, poetry)
- Run all test types (unit, integration)
- File system operations
- Network access
- Code analysis and exploration

**Limitations** ⚠️
- Tests requiring Postgres/Redis **might** fail (services not running in container)
- Tests requiring Docker-in-Docker won't work
- Long-running tests may timeout (5 minute limit per command)

You can install and start services like Postgres inside the container if needed!

## Interactive Usage

After the initial test run, you can:
- Ask about specific test failures
- Re-run individual tests: "Run just tests/test_pregel.py"
- Examine source code: "Show me the code for test_pregel.py"
- Debug issues interactively

The agent will use:
- `run_tests` tool to re-run specific tests
- `shell` tool to examine code or run other commands

### Container Lifecycle

- **First run**: Creates container `langgraph-test-runner`
- **Subsequent runs**: Reuses existing container
- **Cleanup**: `docker rm -f langgraph-test-runner`

## Cron Jobs / Automated Runs

This agent is designed for automated execution:

1. **Deploy to LangSmith**: Deploy this graph to LangSmith
2. **Configure cron**: Set up a cron schedule in the deployment settings
3. **Empty input**: The cron can invoke with an empty message `{}`
4. **Auto-execution**: The agent automatically clones and runs tests

The agent will:
- Clone the repo (or reuse container if available)
- Run tests automatically
- Return results
- Subsequent invocations can ask follow-up questions

Perfect for continuous testing of the LangGraph repository!

## Architecture

The agent implements a standard LangGraph agentic loop:

`START → llm_call → [tool_node → llm_call]* → END`

- **llm_call**: Claude decides whether to run bash commands or respond
- **tool_node**: Executes bash commands via code execution tool
- **State**: Tracks messages, setup status, and recent test output

## Files

- `src/agent/graph.py` - Agent implementation (setup + create_agent)
- `test_agent.py` - Local test script to run agent without Studio
- `langgraph.json` - LangGraph configuration
- `.env` - API keys (ANTHROPIC_API_KEY required)

## Resources

- [LangGraph Docs](https://langchain-ai.github.io/langgraph/)
- [Code Execution Tool](https://docs.langchain.com/oss/python/integrations/tools/anthropic)
- [Anthropic Sandboxing](https://code.claude.com/docs/en/sandboxing)
