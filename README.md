# autonomous-multi-agents

An autonomous LangGraph agent that reads a crash log, inspects a sandboxed
codebase, patches it, and re-runs the test suite until it passes (or a
turn budget runs out).

It is intentionally narrow in scope: one codebase directory, one test command, three tools(read a file, write a file, run tests). The design priority is **safety and predictability of an LLM-driven agent that can write to disk and execute code**, not the breadth of features.

## How it works
The agent is a small state machine with two nodes, `agent` and `tools`, looping until the model stops asking for tools or a turn budget is hit.

```
                      ┌─────────────┐
                      │    START    │
                      └──────┬──────┘
                             │
                             ▼
                    ┌─────────────────────┐
                    │     REASONING       │◄────────────────────┐
                    │       (LLM)         │                     │
                    └──────────┬──────────┘                     │
                               │                                │
                          tool calls?                           │
                       ╱              ╲                         │
                      no              yes                       │
                      │                │                        │
                      ▼                ▼                        │
                 ┌─────────┐     ┌────────────────┐             │
                 │   END   │     │     TOOLS      │             │
                 └─────────┘     │  view_codebase │             │
                                 │ patch_codebase │──────►tool results
                                 │   run_pytest   │ 
                                 └────────────────┘
```
 
Each pass through `reasoning` increments an `attempts` counter in graph
state. `should_continue` checks `attempts >= MAX_ATTEMPTS` **before**
checking whether the model still wants to call tools — so the run always
terminates with a clean summary instead of looping forever, even if the
model insists on trying again.
 
**Tool call flow for a typical run:**
 
1. `main.py` seeds the graph with a `HumanMessage` containing the crash
   log / error payload.
2. `reasoning` node calls the LLM with the system prompt + message
   history.
3. If the LLM requests `view_codebase`, the `tools` node reads the file
   (sandboxed — see [Safety guarantees](#safety-guarantees)) and returns
   its contents as a `ToolMessage`.
4. The LLM proposes a fix and calls `patch_codebase` with the **full new
   file contents** (not a diff — every patch is a whole-file overwrite).
5. The LLM calls `run_pytest_suite`; the result (`PASS`/`FAIL` + logs) is
   fed back.
6. Loop continues until tests pass, the model stops on its own, or
   attempts run out.
---

## Project Structure
```
autonomous-multi-agents/
├── agent/
│   ├── config.py              # all tunables, env-var driven
│   ├── state.py               # LangGraph state schema
│   ├── security.py            # path sandboxing (traversal/symlink/ext checks)
│   ├── tools/
│   │   ├── file_ops.py        # safe read/write, always routed through security.py
│   │   ├── test_runner.py     # subprocess pytest runner, with timeout
│   │   └── langchain_tools.py # @tool wrappers exposed to the LLM
│   └── graph/
│       ├── nodes.py           # reasoning_node, tool_execution_node
│       ├── routing.py         # should_continue (with attempt cap)
│       └── build.py           # graph assembly
├── codebase/                  # <- the target app being fixed lives here
├── tests/                     # tests for the agent itself, not the target app
├── main.py                    # CLI entrypoint
└── requirements.txt
```

## Setup
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```


## Usage
Point the agent at a log file:
```bash
python main.py path/to/crash.log
```
Or pass the error payload inline:
```bash
python main.py --text "ZeroDivisionError: division by zero at app.py line 2"
```
 
The repo ships with a mock FastAPI service (`codebase/app.py`) that has
two seeded bugs(for now) you can reproduce and hand to the agent:
 
```bash
uvicorn codebase.app:app --reload            # terminal 1
python codebase/simulation.py zero_division  # terminal 2, or: key_error
python codebase/monitor.py                   # turns app.log into incidents.jsonl
```
 
The agent will read/patch files under `codebase/` only — it cannot escape
that directory (see `agents/security.py`). At the end of a run it prints
the number of reasoning turns used and the model's final summary.
 
---
