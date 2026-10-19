# Canvas LMS Skill

## Setup

Requires `CANVAS_API_KEY` and `CANVAS_URL`, read from the environment or from a
`.env` file in the skill directory:

```
CANVAS_API_KEY=your_canvas_api_token
CANVAS_URL=https://your-school.instructure.com
```

Get a token in Canvas → Account → Settings → + New Access Token.
`CANVAS_URL` is the bare host, no `/api/v1` suffix and no trailing slash.

## Usage

One script handles everything. Run it with `run_bash_command`, defining `$CLI`
in the same command since shell variables do not persist between calls:

```bash
CLI=~/.gemini/config/skills/canvas-cli/scripts/canvas_cli.py
python3 $CLI <command> [args]
```

### Deterministic Token Shielding (Kem Glitch Architecture)
To eliminate context bloat and token exhaust in agent loops, always use the deterministic projection flags:
- `--table` (`-t`): Formats output as a high-density Markdown table (**~95% token reduction** compared to raw JSON).
- `--project <keys>` (`-p`): Strictly limits fields to a comma-separated list (e.g. `--project id,name,due_at`).
- `--out <file>` (`-o`): Buffers bulk JSON payloads directly to disk and prints a concise 1-line receipt with preview.
- `--limit <N>` (`-n`): Caps the number of returned records.
- `--format [table|json|ids]`: Select exact rendering format.

## Commands

### ⚡ Urgent Action Items & Deadlines (Cross-Course)
```bash
# 1. Actionable student todo items across all enrolled courses (ultra-compact)
python3 $CLI todo --table

# 2. Upcoming deadlines in the next 14 days across all active courses
python3 $CLI upcoming --table
python3 $CLI upcoming --days 7 --table
```

### Courses
Find course IDs first — they are the argument to nearly everything else:

```bash
# Active enrolled courses rendered as a compact token-efficient table
python3 $CLI courses --enrollment-state active --summary --table

# Project strictly course ID and code
python3 $CLI courses --project id,course_code --table

# Buffer 100 courses to disk to shield agent context
python3 $CLI courses --out /tmp/all_courses.json

# Course syllabus / reading list (returns the raw body, not JSON)
python3 $CLI courses --course-id 12345 --syllabus
```

`12345` below is a course ID. `self` can be used anywhere a user ID is accepted.

### Assignments

```bash
# All assignments (--summary produces compact token-friendly output)
python3 $CLI assignments 12345 --summary

# Full assignment details
python3 $CLI assignments 12345

# One assignment
python3 $CLI assignments 12345 --assignment-id 99

# Per-student due-date extensions
python3 $CLI assignments 12345 --assignment-id 99 --overrides

# Create (instructor tokens only)
python3 $CLI assignments 12345 --create \
  --name "Chapter 5 Quiz" --points 50 --due-at "2026-03-30T23:59:00Z"
```

### Submissions and grades

```bash
# One submission
python3 $CLI submissions 12345 --student-id 456 --assignment-id 99

# One student's submissions, filtered
python3 $CLI submissions 12345 --student-id 456 \
  --assignment-ids 99 --assignment-ids 100 --graded true

# Everything submitted in a course
python3 $CLI submissions 12345

# Your grades / the full gradebook
python3 $CLI grades 12345 self
python3 $CLI gradebook 12345
```

### Course content

```bash
python3 $CLI modules 12345                    # modules
python3 $CLI modules 12345 --module-id 5 --items  # readings, files, pages in a module
python3 $CLI files 12345                     # files
python3 $CLI files 12345 --file-id 77
python3 $CLI pages 12345                     # wiki pages
python3 $CLI pages 12345 --url "lecture-notes"
python3 $CLI quizzes 12345
python3 $CLI discussions 12345
python3 $CLI enrollments 12345 --type Student --state active
python3 $CLI outcomes 12345
```

### Announcements

```bash
python3 $CLI announcements 12345
python3 $CLI announcements 12345 --announcement-id 12
```

### Calendar

```bash
python3 $CLI calendar \
  --context course_12345 --start-date 2026-03-01 --end-date 2026-03-31

# Several courses at once
python3 $CLI calendar \
  --context course_12345 --context course_67890
```

### Users and write operations

```bash
python3 $CLI users self --include enrollments
python3 $CLI progress 999    # async op status
```

Creating content (`--create` on assignments, announcements, modules,
discussions, quizzes, pages) requires an instructor or admin token; a student
token gets 403. `--add-item` on modules adds an item to an existing module.

### OCR & Document Conversion (Handwritten & Scanned PDFs)

For scanned worksheets, lecture slides, and handwritten tutorial solutions:

```bash
OCR_CLI=~/.gemini/config/skills/canvas-cli/scripts/pdf_ocr.py

# Automatically detect scanned pages and transcribe via LightOnOCR to Markdown LaTeX
python3 $OCR_CLI "path/to/Tutorial Solutions.pdf" -o "markdown/Tutorial_Solutions.md"

# Transcribe specific pages
python3 $OCR_CLI "path/to/Tutorial Solutions.pdf" --pages 1 2 3 -o "markdown/Tutorial_P1-3.md"

# Force OCR even if document contains digital text
python3 $OCR_CLI "path/to/document.pdf" --force-ocr -o "markdown/output.md"
```

## Notes

- Timestamps are ISO 8601: `2026-03-30T23:59:00Z` for UTC, or with an offset
  such as `2026-03-30T23:59:00-04:00`.
- Rate limits and transient 5xx errors are retried automatically with backoff,
  honouring `Retry-After`. Requests time out after 30s.
- **Error handling**: `401` = token invalid/expired. `403` = token lacks the
  permission (e.g. a student creating an assignment). `404` = wrong ID or no
  access. Errors print the HTTP status and Canvas's own message to stderr and
  exit non-zero; stdout stays clean JSON.

See `references/api_endpoints.md` for the underlying endpoint list.
