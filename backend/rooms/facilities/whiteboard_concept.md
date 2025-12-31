# Whiteboard Concept

The whiteboard acts as the shared, append-only context across room members. Storing it as Markdown keeps the stream human-readable while still being easy to transform into other formats if necessary. A simple structure that works well in practice is:

```markdown
# Problem
<problem definition emitted from `ProblemDefinition.to_problem_string()`>

# Meeting Notes
- <timestamp> <identifier>: <content>
```

This provides clear separation between the original prompt and the collaborative transcript. Agents can render or ingest the document as plain text, and consumers like downstream services or the frontend can parse the headings to extract the relevant sections.

## Suggested Extensions
- **Metadata Block:** Prepend a small front-matter section for session metadata (room id, members, etc.) if richer context is needed.
- **Subsections:** When multiple phases exist (e.g., proposals vs. critiques), nest additional headings such as `## Stage 1 – Proposal` under the meeting notes section.
- **Inline JSON Payloads:** For machine-friendly consumption, allow individual bullet items to embed structured JSON after a delimiter, e.g. `- … | {"score": 0.82}`.
- **Incremental Reads:** Remember the last timestamp you processed and call `whiteboard.read(since=timestamp)` to fetch only the new bullet entries. The response is headed by `# Meeting Notes (Since <timestamp>)` to keep the structure recognizable even when no new notes exist (in which case the body contains `- No new notes.`).

## Sample Whiteboard Snapshot

```markdown
# Problem
## Problem Definition
Design the caching layer for the new analytics dashboard.

# Meeting Notes
- [2025-12-29T17:03:12Z] Analyst-1: Initial concern around cache invalidation with ad-hoc queries.
- [2025-12-29T17:05:47Z] Architect: Suggests a hybrid approach using Redis for hot paths and S3 for cold storage.
- [2025-12-29T17:09:30Z] Analyst-2: Recommends defining TTL tiers based on dashboard segment usage.
- [2025-12-29T17:12:58Z] Moderator: Summarized decisions; action item to prototype Redis tier.
```

To fetch only subsequent updates, agents can remember the last timestamp they observed (e.g., `2025-12-29T17:12:58Z`) and call `read(since=<timestamp>)`. The resulting delta might look like:

```markdown
# Meeting Notes (Since 2025-12-29T17:12:58Z)
- [2025-12-29T17:16:04Z] Moderator: Confirmed Redis prototype scheduled for next sprint.
```

If no new activity has occurred, the response becomes:

```markdown
# Meeting Notes (Since 2025-12-29T17:12:58Z)
- No new notes.
```

This layout keeps the whiteboard concise, legible, and extendable while staying compatible with the current append-only facilities implementation.
