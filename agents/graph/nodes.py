import logging

from typing import Dict, List
from langchain_core.messages import SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from agents.state import AgentState
from agents.config import MAX_ATTEMPTS, MODEL_NAME, MODEL_TEMPERATURE
from agents.tools.langchain_tools import AGENT_TOOLS, TOOL_MAP
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parents[2] / ".env"

load_dotenv(dotenv_path = env_path)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = SystemMessage(
    content=(f"""
    You are an expert Autonomous Site Reliability and DevOps Engineer.
    
    Your task is to fix production bug crashes reported in log files.
    
    Workflow:
    1. Inspect the error payload provided.
    2. Use `view_codebase` to inspect the relevant application and test files.
    3. Determine the bug fix required.
    4. Apply the updated code using `patch_codebase`
    5. Run `run_pytest_suite` to verify your fix.
    
    You have at most {MAX_ATTEMPTS} reasoning turns to complete this task.
    
    After receiving the contents of a file from view_codebase, analyze those contents before calling view_codebase for the same file again.

    Do not call the same tool with the same arguments repeatedly.
    If the file contents are already present in the conversation, use them.
    
    If you exhaust your attempts without all tests passing, clearly summarize in your final message what you tried, 
    and what still fails, and what do you recommend to a human engineer.
    
    Do not claim success unless `run_pytest_suite` has reported PASS.
    """)
)

llm = ChatOpenAI(
    model = MODEL_NAME,
    temperature = MODEL_TEMPERATURE
)
llm_with_tools = llm.bind_tools(AGENT_TOOLS)

def reasoning_node(state: AgentState) -> Dict:
    """
    The brain of the agent.
    
    Analyzes the conversation and decides whether to respond or call a tool.
    """
    messages = state["messages"]
    attempts = state.get("attempts", 0)
    turn = attempts + 1
    
    logger.info("Reasoning start turn=%d, message count=%d", turn, len(messages))
    response = llm_with_tools.invoke([SYSTEM_PROMPT] + messages)
    logger.info("Reasoning complete turn=%d, response_type=%s, content_length=%d", turn, type(response).__name__, len(response.content or ""))
    
    return {
        "messages": [response],
        "attempts": attempts + 1
    }
    
def tool_execution_node(state: AgentState):
    """
    Executes any tool calls emitted by the reasoning node.
    
    Tool failures are caught and converted into ToolMessage error content
    rather than raised, so a single bad call does not crashes the whole graph run.
    """
    last_message = state["messages"][-1]
    tool_outputs: List[ToolMessage] = []
    
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        call_id = tool_call["id"]
        
        logger.info("Executing tool: %s(%r) ", tool_name, tool_args)
        
        if tool_name not in TOOL_MAP:
            result = f"Error: Tool '{tool_name}' does not exist. Available tools: {list(TOOL_MAP)}"
        else:
            try:
                logger.info("Involing tool: %s", tool_name)
                result = TOOL_MAP[tool_name].invoke(tool_args)
                logger.info("Tool result: %r", result)
            except Exception as e:
                logger.exception("Tool %s raised an exception", tool_name)
                result = f"Error: tool '{tool_name}' raised an exception: {e}"
        
        tool_outputs.append(ToolMessage(content=str(result), tool_call_id = call_id))
    return {
        "messages": tool_outputs
    }
    