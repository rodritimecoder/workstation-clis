## Restructure mode

**1. Inventory before touching.** List the tree. For each area note: what it is, when last touched, what refers to it. Never delete or move in this pass.

**2. Find the hidden form.** Ask the owner (or infer and confirm): what is the repeating unit here? Where does work enter and leave? The mess usually contains a real pipeline, library, or map that grew without a skeleton — extract it, don't replace it. Interview the folder the way you'd interview the person.

**3. Classify every file** into one of five roles:
- **Catalog** — identity/routing (becomes or feeds `AGENTS.md` / index files)
- **Contract** — describes how a step works (becomes a `CONTEXT.md`)
- **Factory** — stable reference (→ `_shared/`, `_system/`, or `references/`)
- **Product** — run-specific artifacts (→ stage `output/` or record folders)
- **Dead** — stale, duplicated, or superseded (→ propose `_archive/`, never silently delete)

**4. Propose before moving.** Write the target tree and a migration map (old path → new path → role) to a file in the workspace — `_migration/map.md` — and state it in your reply. Do not block waiting for a reply; the map is the reviewable artifact, and it is what a human reads if they want to. Before any move, enumerate what points at each file: in-vault references, sibling `../` paths, symlinks, and external referrers (deploy scripts, cron, agent configs) that no walk test can see. A file with a live referrer is **held** until every referrer moves with it. See [references/reference-integrity.md](references/reference-integrity.md).

**5. Migrate.** Move files, write the entry file and contracts, de-duplicate toward one-home-per-fact (leave a link where the copy lived if anything might reference it). Separate method from instance: if the structure will be reused elsewhere, the blank template lives apart from this filled-in deployment.

**6. Validate with the walk test.**
