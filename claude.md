# LangGraph Calculator Agent

A simple calculator agent built with LangGraph that performs arithmetic operations using tools. Based on the [LangGraph quickstart](https://docs.langchain.com/oss/python/langgraph/quickstart).

## Quick Start

1. Install dependencies with [uv](https://github.com/astral-sh/uv):
   ```bash
   uv sync
   ```

2. Add your Anthropic API key to `.env`:
   ```bash
   ANTHROPIC_API_KEY=sk-ant-...
   ```

3. Start LangGraph Studio:
   ```bash
   langgraph dev
   ```

4. Open the Studio UI and send a message:
   ```
   What is 15 multiplied by 3?
   ```

## How It Works

The agent uses a simple graph with three nodes:

- **llm_call**: Claude decides whether to use a tool or respond
- **tool_node**: Executes math operations (add, multiply, divide)
- **should_continue**: Routes between tool execution and ending

Graph flow: `START → llm_call → [tool_node → llm_call]* → END`

## Testing Locally

```python
from langchain.messages import HumanMessage
from src.agent.graph import graph

result = graph.invoke({
    "messages": [HumanMessage(content="What is 3 plus 4?")]
})
```

## Files

- `src/agent/graph.py` - Agent implementation
- `langgraph.json` - LangGraph configuration
- `.env` - API keys (ANTHROPIC_API_KEY required)

## Resources

- [LangGraph Docs](https://langchain-ai.github.io/langgraph/)
- [LangGraph Quickstart](https://docs.langchain.com/oss/python/langgraph/quickstart)
