# {Workspace name}

{One sentence: what this workspace is and what leaves it.}

Built on ICM: folders carry sequencing, hierarchy carries context, files carry state. The structure is the documentation — if something needs explaining, the explanation goes in that folder's CONTEXT.md, not in your head.

## Not this workspace

Say so and stop, rather than starting the wrong pipeline. This workspace is the wrong home when:

- {task that belongs in a different workspace, and where it goes instead}
- {task this workspace does not cover at all}

If the request is close but not this, name the sibling workspace and hand off. Do not improvise a stage.

## Where things live

| Folder | What it holds |
|---|---|
| `stages/` | the pipeline, in execution order |
| `_shared/` | factory: rules and reference that never change per run |
| `_templates/` | blank starters — new work is a copy, not a blank page |
| `setup/` | one-time factory configuration |

## Route by what just happened

| If | Go to | Then stop at |
|---|---|---|
| starting a new run | `stages/01_.../CONTEXT.md` | the stage's output file |
| {previous stage} output ready | next numbered stage | the stage's output file |
| asked for status | scan `stages/*/output/` | report what exists |
| a stage reports STALE | re-run that stage, then every stage after it | — |
| asked to start over | read *Re-running* below first | do not delete anything yet |
| setting up for a new user | `setup/questionnaire.md` | answers written to `_shared/` |

## The one rule

Every stage output is an edit surface: a plain file you can open, change, and save. The next stage reads whatever is there. A human may review a stage's output before the next one starts — that is a choice at the handoff, not a lock on the pipeline.

## Status

Scan `stages/*/output/`. A stage is:

| State | When |
|---|---|
| `PENDING` | no files in `output/` (ignoring `.gitkeep`) |
| `COMPLETE` | has files, and every file is newer than the previous stage's newest file |
| `STALE` | has files, but at least one is **older** than the previous stage's newest file |

`STALE` means someone edited an upstream output after this stage ran, so this stage's result no longer reflects its input. It is the common case after a hand-edit, and it is invisible to a plain presence check.

```
Pipeline Status: {workspace}

  [01-name]  ->  [02-name]  ->  [03-name]
   COMPLETE      STALE         PENDING
```

Report `STALE` with the stage that caused it: "03 is stale because 02's output changed on <date>". Then re-run that stage and everything after it.

## Re-running

Never clear an `output/` folder to start again. Deleting a stage's output destroys the handoff record and cannot tell you what pointed at those files.

Instead, keep runs side by side:

1. Start the new run in the same stage folder; write to new filenames carrying a run marker (`<topic>-2026-03-30.md`).
2. Say in the report which run each stage's current files belong to.
3. Once the new run is complete and you are happy with it, remove the superseded files — and only then check for referrers first (see `references/reference-integrity.md` if this workspace is being restructured).

Re-running a single stage is safe and needs none of this: overwrite that stage's `output/` and let every later stage read the new result. Later stages then report `STALE` until re-run, which is the point.
