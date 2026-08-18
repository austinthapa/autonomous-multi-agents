from langgraph.graph import StateGraph, START, END
from agents.state import AgentState
from agents.graph.nodes import reasoning_node, tool_execution_node
from agents.graph.routing import should_continue

def build_graph():
    builder = StateGraph(AgentState)
    
    builder.add_node("reasoning", reasoning_node)
    builder.add_node("tools", tool_execution_node)
    
    builder.add_edge(START, "reasoning")
    builder.add_conditional_edges(
        "reasoning",
        should_continue,
        {
            "tools": "tools",
            "end": END
        }
    )
    builder.add_edge("tools", "reasoning")
    
    return builder.compile()

agent_graph = build_graph()