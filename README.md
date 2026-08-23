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
 
 Example output:
 ```
 ==============================
AGENT RUN COMPLETE
==============================
Reasoning turns used: 7
------------------------------
All tests have passed successfully. Here's a summary of the changes made:

1. **Fixed ZeroDivisionError in `checkout_item`:** 
   - Added a check to ensure that the `quantity` is greater than zero before attempting the division operation. If the `quantity` is zero or negative, an `HTTPException` with a 400 status code is raised.

2. **Handled KeyError in `get_user`:**
   - Modified the `get_user` function to catch the `KeyError` when a user ID is not found in the `USER_DB`. It now raises an `HTTPException` with a 404 status code and a "User not found." message.

These changes ensure that the application handles invalid inputs gracefully and returns appropriate HTTP responses.
```
---

## Safety guarantees

This agent lets an LLM write files and execute a subprocess autonomously,
so the guardrails are the most important part of the codebase, not an
afterthought:

- **Path sandboxing** (`sre_agent/security.py`) — every `file_name` argument
  from the LLM is resolved to an absolute path and checked against
  `CODEBASE_ROOT`. This blocks:
  - `../../` relative traversal
  - absolute paths (`/etc/passwd`)
  - symlinks that resolve outside the sandbox (checked post-resolution,
    not on the raw string)
  - disallowed file extensions (only `.py .txt .md .cfg .ini .toml` by
    default)

  Violations return an error string to the LLM (so it can self-correct)
  rather than raising — but never touch the filesystem.

- **Loop bound** (`sre_agent/graph/routing.py`) — `should_continue` checks
  `attempts >= MAX_ATTEMPTS` *before* checking whether the model wants to
  keep going. A model that can't fix the bug terminates with a summary
  instead of looping until the process is killed or the API bill runs
  away.

- **Tool error isolation** (`sre_agent/graph/nodes.py`) — any exception
  raised inside a tool call is caught and turned into `ToolMessage` error
  content instead of crashing the graph. A malformed argument or a
  transient I/O error doesn't end the run.


- **Atomic writes** (`sre_agent/tools/file_ops.py`) — patches are written
  to a temp file and renamed into place, so a crash mid-write can't leave
  a half-written source file behind.

What this does **not** protect against — see [Known limitations](#known-limitations).

---

## Testing

Run the agent's own test suite (sandbox + tool wrapper tests):

```bash
pytest tests/ -v
```

The most important file is `tests/test_security.py` — it directly proves
traversal, absolute-path, and symlink-escape attempts are rejected, using
a throwaway `tmp_path` sandbox for isolation.

---

## Troubleshooting

**"Tool command not found" / `FAIL: test command not found`**
`pytest` isn't on `PATH` inside the environment the subprocess inherits.
Activate the same venv you installed `requirements.txt` into before
running `main.py`.

**Agent reports it's out of attempts without a passing suite**
Check the logged reasoning turns (`SRE_AGENT_LOG_LEVEL=DEBUG`) to see
what it tried. Common causes: the bug requires touching a file outside
`ALLOWED_EXTENSIONS` (e.g. a config file), or `MAX_ATTEMPTS` is too low
for the complexity of the fix — raise `SRE_AGENT_MAX_ATTEMPTS` in `.env`.

**`ERROR: ... resolves outside the sandboxed codebase directory`**
This is the sandbox working as intended — the LLM asked to touch a path
outside `codebase/`. If your target app legitimately spans multiple
directories, point `SRE_AGENT_CODEBASE_ROOT` at their common parent
rather than disabling the check.

**Test suite times out**
Either the target app has a genuine hang, or a patch introduced one.
Raise `SRE_AGENT_TEST_TIMEOUT` only if you've confirmed it's the former.

---

## Extending the agent

- **New tools**: add the underlying function under `sre_agent/tools/`,
  wrap it with `@tool` in `langchain_tools.py`, add it to `AGENT_TOOLS`.
  It will automatically be available to the LLM and routed through
  `tool_execution_node`'s error handling.
- **Different LLM provider**: swap `ChatOpenAI` in
  `sre_agent/graph/nodes.py` for another LangChain chat model that
  supports `.bind_tools()`.
- **Git-based rollback**: wrap `codebase/` in a git repo and have
  `patch_codebase_file` commit per write; a wrapper tool could then
  `git revert` if a patch regresses `run_pytest_suite`.

---

## Known limitations

- **No diff/undo beyond atomic single-file writes.** Patches overwrite
  whole files; there's no history across attempts other than what's in
  the message log. Pair with git if you need real rollback.
- **No OS-level sandboxing.** `run_pytest_suite` executes as a subprocess
  with the same permissions as the agent process — the timeout stops
  hangs, not malicious code. If the target codebase is untrusted, run
  the whole agent inside a container (e.g. Docker with a read-mostly
  filesystem and no network).
- **No retry/backoff on LLM API errors.** A transient `ChatOpenAI` failure
  currently propagates and ends the run. Consider wrapping the call in
  `sre_agent/graph/nodes.py` with `tenacity` for production use.
- **Single codebase, single test command.** The agent isn't multi-repo or
  multi-suite aware; that's a deliberate scope limit, not an oversight.

---

## License

Add your license of choice here (e.g. MIT, Apache-2.0).
