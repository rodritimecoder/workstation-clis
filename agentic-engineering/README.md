# agentic-engineering

Autonomous production pipeline implementing **Kem's (Glitch Cat Club) 7-Step Architecture**: moving from conversational chatting to an autonomous, multi-model execution factory.

## The 7-Step Blueprint
1. **Inbound Stream**: Issues or briefs enter `.kanban/01_new/`.
2. **Task Board**: Local Markdown Kanban state machine (`new` -> `picked_up` -> `review` -> `done`).
3. **The Listener**: Event-driven watcher that automatically claims ready cards.
4. **Report Block & Unbiased Judge**: Deterministic code gates + fresh-context judge evaluation (Kem's pink arrow `SENT BACK` on failures).
5. **The Splitter**: Partitions approved specs into parallel single-writer lanes.
6. **Multi-Model Sandboxes**: Concurrently executes tasks across Opus, Sonnet, and local models in isolated sandboxes.
7. **Delivery to YOU**: Verified PR / deliverables presented cleanly for human review.

## Quickstart
```bash
# 1. Initialize Kanban in any project
agentic init /path/to/project

# 2. View board
agentic kanban list

# 3. Add a task card
agentic kanban add "Build User Authentication" --req "JWT auth endpoint"

# 4. Run full loop
agentic run CARD-001
```
