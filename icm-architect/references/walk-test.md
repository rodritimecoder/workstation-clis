## The walk test

Validate any ICM — new or restructured — by walking it cold, as an agent with no memory:

- Open the root. Can you answer *where am I* and *where do I go for the current task* within the entry file plus at most two more reads?
- Pick any stage/node. Does its contract name exact input paths, the job, the output, and the human check?
- Can you state pipeline status purely by scanning what exists in `output/` folders (or node frontmatter)? A `COMPLETE`/`PENDING` split is not enough — a stage whose output predates its input's newest edit is `STALE`, and the entry file must say how to detect that.
- If the workspace is about to be re-run or restarted, is there a documented non-destructive path? “Clear the output folders” is not one — the entry file must say how to keep runs side by side or overwrite a single stage.
- Is any routing file carrying content payload? Move the payload to a shelf; leave a pointer.
- Is any fact stored in two places? Pick one home; link from the other.
- Token check: entry file + one contract + its inputs should land in roughly 2k–8k tokens.
- System map only: can a cold agent answer *what is X* and *what else moves if I change X* from `map/AGENTS.md` plus one card? Extra checks are in [references/system-map.md](references/system-map.md).

If a step fails, fix the structure — not by explaining more, but by moving or splitting files until the walk works.
