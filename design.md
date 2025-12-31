## LLM Council Service Design

### Overview
- **Purpose:** Coordinate a council of LLM-backed agents that collectively analyze problems, critique each other’s responses, and synthesize a final deliverable.
- **Approach:** Model the interaction as a room-based session orchestrated by `backend.rooms.room.Room` implementations. Each session selects from a palette of stages (e.g., proposal, critique, synthesis) that can run sequentially, individually, or in parallel while emitting rich telemetry through the monitoring subsystem.

### Goals & Non-Goals
- **Goals:**
	- Support arbitrarily complex problem statements via `backend.primitives.problem_definition.ProblemDefinition` (problem, optional context, metadata).
	- Encapsulate agent behavior behind the `backend.members.council_member.CouncilMember` protocol so any LLM client can participate.
	- Allow multiple orchestration strategies by swapping `Room` implementations without changing the higher-level service contracts.
	- Capture room activity (events, rankings, deliverables) for downstream consumption and observability.
- **Non-Goals:**
	- Hard realtime guarantees; timeouts provide best-effort control but do not replace full preemption.
	- Persisting detailed room telemetry beyond the deliverable payloads (historical analytics can be added later).
	- UI-specific behavior; the frontend consumes deliverables and metadata but is out of scope for this document.

### High-Level Architecture
- **API Layer (`backend/main.py`):** FastAPI endpoints manage conversations, accept user prompts, and invoke the council workflow.
- **Council Orchestrator (`backend/council.py` & `backend/council_service.py`):** Provides reusable primitives for the three-stage process and the service facade for launching sessions. `CouncilService` instantiates rooms, injects members, and enforces overall timeouts.
- **Room Engine (`backend/rooms/*.py`):** Defines the contract (`Room` protocol) and concrete implementations such as `OriginalCouncilRoom` that drive stage progression and deliverable assembly.
- **Members (`backend/members/*.py`):** `CouncilMember` protocol with `AgentMember` implementation backed by `agent_framework.ChatAgent` and Azure AI deployments created by `AgentMemberFactory`.
- **Monitoring (`backend/rooms/monitoring/*.py`):** `Monitor` publishes `RoomEvent` instances to `Subscriber` implementers, enabling observers (e.g., live dashboards, logs) to track session progress.
- **Facilities (`backend/rooms/facilities/whiteboard.py`):** Shared state primitives (thread-safe whiteboard) that rooms can use for collaboration artifacts.
- **Persistence (`backend/storage.py`):** Persists conversation history and metadata for the API layer (not covered in-depth here but remains the consumer of deliverables).

### Core Abstractions
- **Problem Definition (`ProblemDefinition`):**
	- Encapsulates the problem statement, optional contextual background, and structured metadata (`Metadata`).
	- Provides `to_problem_string()` for prompt framing to members and evaluators.
- **Council Members (`CouncilMember`, `AgentMember`):**
	- Protocol requires `think_and_respond(problem: str)` returning a `Response` (content plus reasoning JSON-serializable via `to_json`).
	- `AgentMember` delegates to `ChatAgent` threads; `AgentMemberFactory` provisions Azure-hosted models with unique personas.
- **Deliverable (`Deliverable`):**
	- Aggregates the final synthesis, embeds the original problem, and attaches metadata such as rankings and label mappings.
	- `to_deliverable_string()` produces canonical output for storage or presentation.
- **Room Protocol (`Room`):**
	- Lifecycle: `kickoff()` → `close()` with `RoomStatus` transitions limited to `Inactive`, `Active`, and `Closing`; constructors perform all resource/member wiring so there is no standalone `setup()` stage.
	- `kickoff()` drives the room-specific orchestration plan, allowing single-stage runs, partial workflows, or parallel stage execution.
	- Telemetry: Every room exposes a `Monitor` as part of the protocol, ensuring consistent instrumentation hooks for observers.
	- Facilities: Rooms compose optional shared utilities from `backend.rooms.facilities` (e.g., `Whiteboard`) and can extend with additional facilities without altering the protocol.
	- Concrete rooms coordinate members, manage shared facilities/state, and emit monitoring events.
- **OriginalCouncilRoom:**
	- Provides the reference implementation of the three-stage council workflow executed sequentially.
	- Stage palette:
		1. **Stage 1 – Proposal:** members answer the problem prompt in parallel and persist responses.
		2. **Stage 2 – Critique:** anonymized responses are ranked by council models, yielding label-to-member mappings and peer feedback.
		3. **Stage 3 – Synthesis:** a chairman model synthesizes the final output informed by prior stages.
	- Generates a `Deliverable` that collates the final synthesis, individual responses, rankings, and aggregate statistics.
- **RoundRobinRoom:**
	- Facilitates a single round of sequential contributions; each member responds in turn with prior statements provided as context.
	- During `close()`, every member offers a concluding statement, producing a deliverable that records both the initial round and the ordered conclusions.
- **Monitor & Subscribers:**
	- `Monitor` hosts an asyncio queue of `RoomEvent` objects, dispatching to registered `Subscriber` instances until shutdown or disposal.
	- Provides cooperative cancellation, graceful completion/error notifications, and ensures subscriber cleanup via `AsyncSubscription` disposables.
	- Event schema (`RoomEvent`) is intentionally minimal (type + payload) so rooms can define domain-specific payload contracts.
	- `MemoryBufferSubscriber` offers an in-memory log of recent events with bounded capacity, supporting read-and-flush snapshots for diagnostics or API queries.

### Session Lifecycle
1. **Session Creation:**
	 - API receives user prompt, constructs `ProblemDefinition`, and delegates to `CouncilService`.
	 - `CouncilService` uses `AgentMemberFactory` to provision `ChatAgent`-backed members and instantiates the chosen `Room` (currently `OriginalCouncilRoom`).
2. **Room Instantiation & Prep:** `CouncilService` instantiates the chosen room; the constructor binds members, problems, facilities, and telemetry while the room stays `Inactive` until kickoff.
3. **Kickoff:**
	 - `room.kickoff()` transitions the room to `Active` while it orchestrates the room-defined sequence or subset of stages, supporting sequential or parallel execution.
	 - Rooms may emit `RoomEvent` updates (e.g., “stage_started”, “response_received”) via `Monitor` to subscribed observers.
4. **Close:**
	 - `room.close()` moves the room into the `Closing` state, compiles the `Deliverable`, attaches metadata, and returns to the caller.
	 - On timeout or error, `CouncilService` cancels kickoff and invokes `room.close()` for partial artifacts.
5. **Persistence & Response:** API stores deliverable outputs, updates conversation summaries, and streams results back to the frontend.

### Monitoring & Telemetry
- Rooms publish domain events through the `Monitor` to enable asynchronous observers (e.g., WebSocket broadcasters, log aggregators, memory buffers).
- Subscribers implement `on_room_event`, `on_completed`, and `on_error` to react to lifecycle changes. `Monitor` enforces backpressure via an internal queue and per-subscriber cancellation tokens.
- Future subscribers (`memory_buffer_subscriber.py`) can capture rolling transcripts for debugging or user visibility.

### Concurrency & Reliability
- **Async Orchestration:** Core operations rely on asyncio (`asyncio.create_task`, `asyncio.wait_for`, `asyncio.as_completed`) to parallelize member calls and enforce deadlines.
- **Timeout Handling:** `CouncilService` enforces a per-session timeout; room kickoff tasks are cancelled and cleaned up safely if exceeded.
- **Error Propagation:** Room operations surface exceptions to callers; monitor safeguards ensure one subscriber failure does not compromise others.
- **Resource Cleanup:** Rooms use async context managers (`__aenter__`/`__aexit__`) to ensure proper cleanup of agent resources regardless of how the session ends.

### Extensibility Directions
- **Alternative Room Strategies:** Implement additional `Room` subclasses (e.g., multi-round debate) that customize which stages run, in what order, and with what concurrency, then register selection via `room_type`. `backend.rooms.round_robin_room` provides a sequential reference implementation.
- **Richer Facilities:** Extend whiteboard capabilities (summaries, structured artifacts) and expose them via events.
- **Adaptive Membership:** Allow heterogeneous agents (different models per role, dynamic joining/leaving) by expanding `AgentMemberFactory` policies.
- **Enhanced Monitoring:** Implement concrete subscribers (storage sinks, analytics pipelines, live dashboards) hooking into the `Monitor`.
- **Deliverable Variants:** Support multi-format outputs (structured JSON, knowledge graphs) by extending `Deliverable` schema and metadata conventions.

### Open Questions & Future Work
- How should long-running or multi-turn sessions manage agent memory (currently per-agent thread cached in `AgentMember`)?
- Should monitor events be persisted for auditability, and if so, which storage and retention policies apply?
- What admission control or scaling strategies are required as agent counts or model latencies grow?
- Can we unify the FastAPI three-stage orchestration (`backend/council.py`) with room-level implementations to reduce duplication?

## Agent Thread & Tool Call Persistence Design

### Objectives
- **Auditability:** Capture every agent exchange (prompts, responses, tool calls/results) for debugging, compliance, and replay.
- **Continuity:** Allow agents to resume threads across sessions without losing context; support warm restarts after failures.
- **Observability:** Surface structured tool-call telemetry to monitors/frontends without scraping raw logs.

### Data Model
1. **Thread Record**
	- `thread_id`, `member_id`, `room_id`, `session_id`, timestamps (created/updated/closed).
	- Status enum (active, paused, archived).
2. **Message Table**
	- Ordered entries with `role` (system/user/assistant/tool), `content` (JSONB), `tool_call_ids`, `response_metadata` (latency, tokens, model).
	- Foreign key to thread.
3. **Tool Call Table**
	- `tool_call_id`, `tool_name`, serialized arguments, execution status, response payload, error info, duration metrics.
	- Links back to both the triggering message and any tool response messages.

### Lifecycle Integration
- **AgentMember Hooks:**
  - When `_agent.run` is invoked, record an outbound message entry containing the prompt/context.
  - On receiving the result, log assistant messages as well as tool calls. For each tool call, enqueue a persistence task that writes the tool invocation before execution and updates it after completion.
  - Tool wrappers (e.g., `VoteBox.vote`) return structured payloads; a decorator can auto-log arguments/results.
- **Thread Persistence API:**
  - Provide `ThreadRepository` with async methods: `append_message`, `log_tool_call`, `close_thread`, `fetch_thread_history`.
  - Inject repository into `AgentMember` (or underlying ChatAgent) so persistence is pluggable (e.g., Postgres, CosmosDB).

### Storage & Retention
- **Primary Store:** relational DB (Postgres) to leverage transactions and JSONB columns for flexible payloads.
- **Archival:** old threads can be compacted (store references to transcript blobs in object storage) while keeping tool-call metadata hot.
- **Privacy Controls:** allow redaction policies before persisting (e.g., strip PII fields in tool args/results).

### Replay & Monitoring
- Build a `ThreadReplayService` that can reconstruct a conversation for debugging or rerun it against a different model.
- Extend the monitoring pipeline to emit summarized tool-call events (tool name, latency, status) so dashboards can track usage.

### Implementation Steps
1. Define DB schema/migrations for threads, messages, and tool calls.
2. Implement `ThreadRepository` with async CRUD operations and configure dependency injection.
3. Add persistence hooks in `AgentMember` (message logging) and tool adapters/decorators (tool call logging).
4. Update monitoring/subscriber system to optionally consume persisted thread IDs for cross-linking.
5. Provide admin/debug endpoints to fetch transcripts and tool-call histories for a session.

