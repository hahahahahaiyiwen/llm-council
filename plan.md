## Council Service Improvement Plan

### 1. Broaden Capabilities (Tools & Rooms)
- **New Tool Suite:** curate reusable tools (vote, research, calculator, knowledge lookup). Define standard interfaces, shared context state, and telemetry logging for each tool.
- **Tool Lifecycle:** build registration/initialization hooks in `AgentMemberFactory` so agents receive tool bundles based on room needs while keeping shared instances (e.g., `VoteBox`).
- **Room Variants:** design additional `Room` subclasses (debate, brainstorming, critique-only). Each room should document stages, member roles, and deliverable format extensions.
- **Facility Enhancements:** upgrade `Whiteboard` to store structured artifacts (agenda, decisions) and allow rooms/tools to read/write specific channels.
- **Testing & Telemetry:** add scenario tests per room type and extend monitoring events so frontend and ops can differentiate workflows.

### 2. Iterative Quality Loop
- **Reviewer Role:** introduce a dedicated quality reviewer (could be an agent or human-in-the-loop) that scores deliverables using explicit rubrics (alignment, completeness, actionability).
- **Session Iteration:** update `CouncilService` to support multiple iterations: after `room.close()`, pass deliverable to reviewer; if below threshold, trigger:
	1. **Refinement session:** re-run original problem with reviewer feedback appended.
	2. **Problem decomposition:** have a planning agent split the problem into sub-problems, run sessions per sub-problem, then synthesize.
- **Execution Graph:** represent iterations/sub-sessions in a plan tree; reuse `ProblemDefinition` metadata to track lineage and merge results.
- **Orchestration Controls:** add policies for max iterations, parallel sub-sessions, and timeout budgeting across spawned rooms.
- **Evaluation Metrics:** persist reviewer scores and iteration counts for analytics; expose to frontend so users see why multiple runs occurred.

### Next Steps
1. Prototype a generic tool registry and convert existing vote tool to the new model.
2. Draft specifications for two new room types and implement one end-to-end.
3. Design the reviewer workflow (prompt, thresholds) and extend `CouncilService` to orchestrate retries/decomposition.
4. Measure latency/cost impacts, then iterate on heuristics for when to branch or stop.
