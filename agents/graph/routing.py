import logging

from typing import Literal
from agents.state import AgentState
from agents.config import MAX_ATTEMPTS
from langchain_core.messages import AIMessage

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def should_continue(state: AgentState) -> Literal["tools", "end"]:
    """
    Determines whether to route to tool execution or terminates the workflow.
    
    Terminates when:
        - The model stops requesting tool calls (When it believes that it is done) or 
        - MAX_ATTEMPTS has been reached.
    """
    attempts = state.get("attempts", 0)
    last_message = state["messages"][-1]
    
    if attempts >= MAX_ATTEMPTS:
        logger.warning("Max attempts(%d) has been reached; ending the run without confirmed fix.", MAX_ATTEMPTS)
        return "end"
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    
    return "end"
