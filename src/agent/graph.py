"""LangGraph calculator agent.

A simple agent that can perform arithmetic operations using tools.
Based on the LangGraph quickstart guide.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, Literal

from langchain.chat_models import init_chat_model
from langchain.messages import AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langchain.tools import tool
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict


# Define tools
@tool
def add(a: int, b: int) -> int:
    """Add two numbers.

    Args:
        a: First int
        b: Second int
    """
    return a + b


@tool
def multiply(a: int, b: int) -> int:
    """Multiply two numbers.

    Args:
        a: First int
        b: Second int
    """
    return a * b


@tool
def divide(a: int, b: int) -> float:
    """Divide two numbers.

    Args:
        a: First int
        b: Second int
    """
    return a / b


# Set up model with tools
model = init_chat_model("claude-sonnet-4-5-20250929", temperature=0)
tools = [add, multiply, divide]
tools_by_name = {tool.name: tool for tool in tools}
model_with_tools = model.bind_tools(tools)


# Define state
class InputState(TypedDict):
    """Input state - what users provide."""

    messages: Annotated[list[AnyMessage], operator.add]


class State(TypedDict):
    """Full internal state."""

    messages: Annotated[list[AnyMessage], operator.add]
    llm_calls: int


def llm_call(state: Dict[str, Any]) -> Dict[str, Any]:
    """Call the LLM and decide whether to use a tool."""
    return {
        "messages": [
            model_with_tools.invoke(
                [
                    SystemMessage(
                        content="You are a helpful assistant tasked with performing arithmetic on a set of inputs."
                    )
                ]
                + state["messages"]
            )
        ],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }


def tool_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Execute the tool calls."""
    result = []
    last_message = state["messages"][-1]

    # Handle both message objects and dicts
    tool_calls = last_message.tool_calls if hasattr(last_message, "tool_calls") else last_message.get("tool_calls", [])

    for tool_call in tool_calls:
        tool = tools_by_name[tool_call["name"]]
        observation = tool.invoke(tool_call["args"])
        result.append(ToolMessage(content=str(observation), tool_call_id=tool_call["id"]))
    return {"messages": result}


def should_continue(state: State) -> Literal["tool_node", END]:
    """Decide whether to continue with tool execution or end."""
    messages = state["messages"]
    last_message = messages[-1]

    # Handle both message objects and dicts
    tool_calls = last_message.tool_calls if hasattr(last_message, "tool_calls") else last_message.get("tool_calls", [])

    # If the LLM makes a tool call, execute it
    if tool_calls:
        return "tool_node"

    # Otherwise, we're done
    return END


# Build the graph
agent_builder = StateGraph(State, input=InputState)

# Add nodes
agent_builder.add_node("llm_call", llm_call)
agent_builder.add_node("tool_node", tool_node)

# Add edges
agent_builder.add_edge(START, "llm_call")
agent_builder.add_conditional_edges("llm_call", should_continue, ["tool_node", END])
agent_builder.add_edge("tool_node", "llm_call")

# Compile
graph = agent_builder.compile(name="Calculator Agent")
