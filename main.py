import sys
import logging
import argparse

from agents.config import CODEBASE_ROOT
from agents.graph.build import agent_graph
from langchain_core.messages import HumanMessage

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_payload(args: argparse.Namespace) -> str:
    """
    Returns the provided text, or reads and returns the contents of the log file
    if no text was provided.
    """
    if args.text:
        return args.text
    try:
        with open(args.log_file, "r", encoding="utf-8") as file:
            return file.read()
    except OSError as e:
        logger.error("Could not read log file %s: %s", args.log_file, e)
        sys.exit(1)
        
def main():
    parser = argparse.ArgumentParser(description="Autonomous bug-fix agent.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("log_file", nargs="?", help="Path to a crash log file.")
    source.add_argument("--text", help="Raw error payload as a string")
    args = parser.parse_args()
    
    if not args.log_file and not args.text:
        parser.error("Provide a log_file path or --text")
    
    payload = load_payload(args)
    
    logger.info("Starting the Autonomous bug-fix agent. Codebase root: %s", CODEBASE_ROOT)
    
    initial_state = {
        "messages": [HumanMessage(content=f"Production error payload:\n\n{payload}")],
        "attempts": 0
    }
    
    final_state = agent_graph.invoke(
        initial_state
    )
    
    last_message = final_state["messages"][-1]
    print("\n" + "="*30)
    print("AGENT RUN COMPLETE")
    print("="*30)
    print(f"Reasoning turns used: {final_state.get('attempts', '?')}")
    print("-"*30)
    print(getattr(last_message, "content", str(last_message)))
    
    return 0

if __name__ == "__main__":
    raise SystemExit(main())