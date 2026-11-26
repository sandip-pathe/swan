# SWAN chat and research workflow

SWAN chat uses a bounded, read-only workflow. The router is the only model
allowed to select context. Its validated `ChatPlan.sections` is the allowlist
for backend retrieval:

| Tool | Saved context read |
| --- | --- |
| `session` | Exchange calendar/session state |
| `market` | Saved quote and compact analysis snapshots |
| `news` | Saved headline snapshots |
| `weekly` | Saved weekly structure |
| `ideas` | Existing eligible/relevant research ideas |

The router returns a direct answer when no tool is needed. Otherwise SWAN loads
only the selected sections and asks the answer role to explain that evidence.
The workflow does not trigger collectors, browse the web, access broker sessions,
or place orders. Each run has one planning call and at most one answer call. A
provider operation is bounded to 22 seconds in interactive chat, leaving margin
under the web client's 60-second deadline. Separate SQLite leases keep chat
traffic independent from background Insight research. One chat request may be
in flight per API process; additional simultaneous requests receive a bounded
busy response rather than competing for the same model lane.

Daily AI Insight call and token budgets are reserved only by the background
Insight worker. Chat has no daily cap. Provider outages, normal rate limiting,
per-process request serialization and request-size/schema limits still apply.
The worker's provider-call ceiling remains five per IST day, and failures count
against that ceiling.

Chat run traces persist for up to seven days. They record stage, status, chosen
tool names, retrieved section names and sanitized exception types. They never
store the prompt or answer. `GET /api/chat/runs/{run_id}` requires the same
authenticated account that owns the trace. Failed runs return a retryable
response with the run ID; the frontend keeps the question in local conversation
storage.

This fixed state machine is intentional: the chat path has three bounded phases
(route, read selected saved context, answer), while the background Insight path
already has a durable SQLite job queue. A general graph runtime or multi-agent
delegation would add state and failure modes without a current user need. Revisit
LangGraph if a workflow needs durable pause/resume, human approval, conditional
multi-step tool loops, or recovery from intermediate side effects. Keep tool
execution read-only unless a separately reviewed permission workflow explicitly
authorizes a different action.
