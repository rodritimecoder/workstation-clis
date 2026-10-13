#!/usr/bin/env python3
"""
Canvas LMS CLI - Canvas API client driven by a declarative command table.

Reads CANVAS_API_KEY and CANVAS_URL from the environment, falling back to a
.env file in the skill directory.

Each subcommand is declared once in COMMANDS: a name, a one-line description,
an argument spec, and a handler that *returns* data (printing is centralised
in main()).

Argument spec syntax (one per line, whitespace separated):
    name            positional argument; dest is name with underscores
    --name          optional flag
    types:  int float str bool flag(repeatable: append)
    extra:  rep      collect into a list (repeat the flag)
    example: --include rep   ->  --include a --include b
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urljoin
from urllib.request import Request, urlopen

# ── Exceptions ────────────────────────────────────────────────────────────────

class CanvasError(Exception):
    """Base exception for all Canvas CLI errors."""
    pass


class CanvasConfigError(CanvasError):
    """Raised when configuration is missing or invalid."""
    pass


class CanvasHTTPError(CanvasError):
    """Raised when an HTTP error occurs with Canvas API."""
    def __init__(self, code: int, body: str, url: str, method: str):
        self.code = code
        self.body = body
        self.url = url
        self.method = method
        msg = f"HTTP {code} on {method} {url}"
        if body:
            msg += f"\n{body}"
        super().__init__(msg)


class CanvasNetworkError(CanvasError):
    """Raised when network-level failures occur (connection, timeout, DNS)."""
    pass


# ── Config ────────────────────────────────────────────────────────────────────

env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

API_KEY = os.environ.get("CANVAS_API_KEY", "")
_canvas_url = os.environ.get("CANVAS_URL", "").rstrip("/")
API_BASE = f"{_canvas_url}/api/v1" if _canvas_url else ""


def get_headers() -> dict[str, str]:
    key = API_KEY or os.environ.get("CANVAS_API_KEY", "")
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


HEADERS = get_headers()

TIMEOUT = 30
MAX_RETRIES = 4
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})

# ── Slug & Naming Normalization (OKF Standard) ─────────────────────────────────

def clean_okf_slug(title: str, course_code: str | None = None, week: str | int | None = None) -> str:
    """
    Produce a clean, emoji-free, predictable OKF concept slug.
    Format: [course_]w[week_]type_topic-slug
    """
    s = title.strip()
    # Strip emojis and non-ASCII decorative symbols
    s = re.sub(r'[\U00010000-\U0010ffff]', '', s)
    s = re.sub(r'[^\x00-\x7F]+', '', s)
    # Remove file extensions and raw query noise
    s = re.sub(r'\.(md|html|pdf|docx|pptx)$', '', s, flags=re.IGNORECASE)
    # Replace punctuation and separators with single dashes
    s = re.sub(r'[\s_:\-\—\–\/\(\)\,\@\%\&]+', '-', s)
    s = s.strip('-').lower()

    parts = []
    if course_code:
        c_clean = str(course_code).split()[0].lower()
        parts.append(c_clean)
    if week is not None:
        try:
            w_num = int(str(week).lower().replace("week", "").replace("w", "").strip())
            parts.append(f"w{w_num:02d}")
        except ValueError:
            pass
    parts.append(s or "untitled")
    return "_".join(parts)


def _format_param_val(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    return v


def build_url(url: str, params: dict | None) -> str:
    """Append params to url, percent-encoding values, formatting booleans, and repeating list items."""
    if not params:
        return url
    clean = {}
    for k, v in params.items():
        if v is None:
            continue
        if isinstance(v, (list, tuple)):
            clean[k] = [_format_param_val(x) for x in v]
        else:
            clean[k] = _format_param_val(v)
    return f"{url}?{urlencode(clean, doseq=True)}" if clean else url


def request(method: str, url: str, data: dict | None = None) -> tuple:
    """Request with retry/backoff. Returns (status, parsed_json_or_None, headers)."""
    if not API_KEY or not API_BASE:
        raise CanvasConfigError("Set CANVAS_API_KEY and CANVAS_URL in .env file or environment.")

    headers = HEADERS if HEADERS.get("Authorization") != "Bearer " else get_headers()
    body = json.dumps(data).encode() if data is not None else None

    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = urlopen(Request(url, data=body, headers=headers, method=method), timeout=TIMEOUT)
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else None), resp.headers
        except HTTPError as e:
            if e.code in RETRY_STATUSES and attempt < MAX_RETRIES:
                wait = float(e.headers.get("Retry-After") or 2 ** attempt)
                print(f"HTTP {e.code}; retry {attempt + 1}/{MAX_RETRIES} in {wait:.0f}s", file=sys.stderr)
                time.sleep(wait)
                continue
            err_body = e.read().decode(errors="replace")
            raise CanvasHTTPError(e.code, err_body, url, method)
        except (URLError, TimeoutError, OSError) as e:
            if attempt < MAX_RETRIES:
                print(f"{type(e).__name__}: {e}; retry {attempt + 1}/{MAX_RETRIES}", file=sys.stderr)
                time.sleep(2 ** attempt)
                continue
            raise CanvasNetworkError(f"{method} {url} failed: {e}")

    raise CanvasNetworkError(f"{method} {url} failed after {MAX_RETRIES} retries")


def get(path: str, params: dict | None = None) -> dict:
    return request("GET", build_url(f"{API_BASE}{path}", params))[1]


def post(path: str, data: dict) -> dict:
    return request("POST", f"{API_BASE}{path}", data)[1]


def next_page_url(link_header: str, current_url: str) -> str | None:
    """Return the rel="next" URL from a Link header, or None on the last page."""
    for part in link_header.split(","):
        segs = part.split(";")
        if len(segs) < 2 or not segs[0].strip().startswith("<"):
            continue
        if any(s.strip().lower().replace(" ", "") == 'rel="next"' for s in segs[1:]):
            url = segs[0].strip()[1:-1]
            return url if url.startswith("http") else urljoin(current_url, url)
    return None


def paginate(path: str, params: dict | None = None) -> list:
    """Fetch every page of a list endpoint."""
    url = build_url(f"{API_BASE}{path}", {**(params or {}), "per_page": 100})
    items: list = []

    while url:
        _status, payload, headers = request("GET", url)
        if not isinstance(payload, list):
            break
        items.extend(payload)
        # The next URL is absolute and already carries the query string,
        # so follow it verbatim rather than re-appending params.
        url = next_page_url(headers.get("Link", ""), url)

    return items


# ── Handlers ──────────────────────────────────────────────────────────────────

def resource(ns, path: str, id_attr: str, body=None, id_param: str | None = None):
    """Shared get-one / create / list flow used by most course resources."""
    ident = getattr(ns, id_attr, None)
    if ident is not None:
        return get(path, {id_param: ident}) if id_param else get(f"{path}/{quote(str(ident), safe='')}")
    if getattr(ns, "create", False):
        return post(path, body(ns))
    return paginate(path)


# ── Summaries (Token & Context Optimization) ──────────────────────────────────

def summarize_course(c: dict) -> dict:
    return {
        "id": c.get("id"),
        "name": c.get("name"),
        "course_code": c.get("course_code"),
        "workflow_state": c.get("workflow_state"),
        "start_at": c.get("start_at"),
        "end_at": c.get("end_at"),
    }


def summarize_assignment(a: dict) -> dict:
    return {
        "id": a.get("id"),
        "name": a.get("name"),
        "due_at": a.get("due_at"),
        "points_possible": a.get("points_possible"),
        "submission_types": a.get("submission_types"),
    }


def summarize_announcement(an: dict) -> dict:
    author = an.get("author") or {}
    return {
        "id": an.get("id"),
        "title": an.get("title"),
        "posted_at": an.get("posted_at"),
        "author": author.get("display_name") if isinstance(author, dict) else str(author),
    }


def summarize_module(m: dict) -> dict:
    return {
        "id": m.get("id"),
        "name": m.get("name"),
        "position": m.get("position"),
        "items_count": m.get("items_count"),
        "state": m.get("state"),
    }


def title_message(ns) -> dict:
    return {"title": ns.title, "message": ns.message}


def cmd_courses(ns):
    if ns.course_id is None:
        params = {}
        if getattr(ns, "enrollment_state", None):
            params["enrollment_state"] = ns.enrollment_state
        res = paginate("/courses", params if params else None)
        if getattr(ns, "summary", False) and isinstance(res, list):
            return [summarize_course(c) for c in res]
        return res
    if ns.syllabus:
        return get(f"/courses/{ns.course_id}", {"include": ["syllabus_body"]}).get("syllabus_body", "")
    res = get(f"/courses/{ns.course_id}", {"include": ns.include})
    if getattr(ns, "summary", False) and isinstance(res, dict):
        return summarize_course(res)
    return res


def cmd_enrollments(ns):
    return paginate(f"/courses/{ns.course_id}/enrollments", {"type": ns.type, "state": ns.state})


def cmd_assignments(ns):
    c, a = ns.course_id, ns.assignment_id
    if a and ns.overrides:
        return paginate(f"/courses/{c}/assignments/{a}/overrides")
    if ns.create:
        return post(f"/courses/{c}/assignments", {
            "name": ns.name, "description": ns.description or "",
            "points_possible": ns.points, "due_at": ns.due_at,
            "submission_types": ["online_text_entry"],
        })
    res = resource(ns, f"/courses/{c}/assignments", "assignment_id")
    if getattr(ns, "summary", False):
        if isinstance(res, list):
            return [summarize_assignment(x) for x in res]
        if isinstance(res, dict):
            return summarize_assignment(res)
    return res


def cmd_announcements(ns):
    res = resource(ns, f"/courses/{ns.course_id}/announcements", "announcement_id", title_message)
    if getattr(ns, "summary", False):
        if isinstance(res, list):
            return [summarize_announcement(x) for x in res]
        if isinstance(res, dict):
            return summarize_announcement(res)
    return res


def cmd_submissions(ns):
    c = ns.course_id
    ids = ns.assignment_ids or ([ns.assignment_id] if ns.assignment_id else None)
    if ns.student_id and ns.assignment_id:
        return get(f"/courses/{c}/students/{ns.student_id}/submissions/{ns.assignment_id}")
    if ns.student_id:
        return paginate(f"/courses/{c}/students/{ns.student_id}/submissions",
                         {"assignment_ids": ids, "graded": ns.graded})
    return paginate(f"/courses/{c}/students/submissions", {"assignment_ids": ids, "graded": ns.graded})


def cmd_modules(ns):
    c, m = ns.course_id, ns.module_id
    if m is None:
        if ns.create:
            return post(f"/courses/{c}/modules", {"name": ns.name, "position": ns.position})
        res = paginate(f"/courses/{c}/modules")
        if getattr(ns, "summary", False) and isinstance(res, list):
            return [summarize_module(x) for x in res]
        return res
    if ns.items:
        return paginate(f"/courses/{c}/modules/{m}/items", {"include": ["content_details"]})
    if ns.add_item:
        return post(f"/courses/{c}/modules/{m}/items",
                    {"title": ns.title, "type": ns.item_type, "content_id": ns.content_id})
    res = get(f"/courses/{c}/modules/{m}")
    if getattr(ns, "summary", False) and isinstance(res, dict):
        return summarize_module(res)
    return res


def cmd_calendar(ns):
    return paginate("/calendar_events", {
        "context_codes[]": ns.context, "start_date": ns.start_date, "end_date": ns.end_date,
    })


# ── Command table ─────────────────────────────────────────────────────────────

TYPES = {"int": int, "float": float, "str": str}


def str2bool(v: str) -> bool:
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


def build_args(spec: str) -> tuple:
    """Turn an arg spec block into (positionals, optionals) for argparse."""
    positionals, optionals = [], []
    for line in spec.strip().splitlines():
        tokens = line.split()
        if not tokens:
            continue
        name, mods = tokens[0], set(tokens[1:])
        kind = next((t for t in tokens[1:] if t in TYPES or t in ("flag", "bool")), "str")

        opts = {"help": name.lstrip("-").replace("-", " ")}
        if kind in TYPES:
            opts["type"] = TYPES[kind]
        elif kind == "bool":
            opts.update(type=str2bool, nargs="?", const=True, metavar="true|false")
        elif kind == "flag":
            opts["action"] = "store_true"
        if "rep" in mods:
            opts["action"] = "append"

        if name.startswith("-"):
            optionals.append((tuple(name.split("|")), opts))
        else:
            positionals.append((name, opts))
    return positionals, optionals


# name, description, arg spec, handler
COMMANDS = [
    ("courses", "List or get courses", """
        --course-id int   List all courses if omitted
        --enrollment-state str  active | invited_or_pending | completed
        --include rep     e.g. total_scores, syllabus_body
        --syllabus flag   Return just the syllabus body
        --summary flag    Compact JSON summary (id, name, code, state, dates)
    """, cmd_courses),

    ("enrollments", "List course enrollments", """
        course_id int
        --type str        StudentEnrollment | TeacherEnrollment | TaEnrollment
        --state str       active | invited | completed | ...
    """, cmd_enrollments),

    ("assignments", "List, get, or create assignments", """
        course_id int
        --assignment-id int   Get one assignment
        --overrides flag      Per-student due-date extensions
        --create flag
        --name str
        --description str
        --points float
        --due-at str          ISO 8601, e.g. 2026-03-30T23:59:00Z
        --summary flag        Compact JSON summary (id, name, due_at, points, types)
    """, cmd_assignments),

    ("submissions", "Get submissions", """
        course_id int
        --student-id int      Limit to one student
        --assignment-id int   One assignment
        --assignment-ids int rep   Filter by several assignment IDs
        --graded bool         true | false
    """, cmd_submissions),

    ("grades", "Get a user's grades in a course", """
        course_id int
        user_id str       Canvas user ID, or 'self'
    """, lambda ns: get(f"/courses/{ns.course_id}/grades/{quote(ns.user_id, safe='')}")),

    ("gradebook", "Get the full course gradebook", """
        course_id int
    """, lambda ns: get(f"/courses/{ns.course_id}/gradebook")),

    ("announcements", "List, get, or create announcements", """
        course_id int
        --announcement-id int
        --create flag
        --title str
        --message str
        --summary flag        Compact JSON summary (id, title, posted_at, author)
    """, cmd_announcements),

    ("modules", "List, get, or create modules and their items", """
        course_id int
        --module-id int      Target one module
        --items flag         List the module's items
        --add-item flag      Add an item to the module
        --title str          Item title (with --add-item)
        --item-type str      SubHeader | File | Page | Assignment | ExternalUrl
        --content-id int     Content object ID for the item
        --create flag
        --name str
        --position int
        --summary flag       Compact JSON summary (id, name, position, items_count, state)
    """, cmd_modules),

    ("discussions", "List, get, or create discussion topics", """
        course_id int
        --topic-id int
        --create flag
        --title str
        --message str
    """, lambda ns: resource(ns, f"/courses/{ns.course_id}/discussion_topics", "topic_id", title_message)),

    ("files", "List course files or get file metadata", """
        course_id int
        --file-id int
    """, lambda ns: resource(ns, f"/courses/{ns.course_id}/files", "file_id")),

    ("quizzes", "List, get, or create quizzes", """
        course_id int
        --quiz-id int
        --create flag
        --title str
        --description str
    """, lambda ns: resource(ns, f"/courses/{ns.course_id}/quizzes", "quiz_id",
                             lambda a: {"title": a.title, "description": a.description or ""})),

    ("pages", "List, get, or create wiki pages", """
        course_id int
        --url str       Page slug, e.g. lecture-notes-week-3
        --create flag
        --title str
        --body str      HTML
    """, lambda ns: resource(ns, f"/courses/{ns.course_id}/pages", "url",
                             lambda a: {"title": a.title, "body": a.body or ""})),

    ("calendar", "List calendar events", """
        --context str rep    e.g. course_12345 (repeat for several)
        --start-date str     YYYY-MM-DD
        --end-date str       YYYY-MM-DD
    """, cmd_calendar),

    ("users", "Get user info", """
        user_id str       Canvas user ID, or 'self'
        --include rep     e.g. avatar, enrollments
    """, lambda ns: get(f"/users/{quote(ns.user_id, safe='')}", {"include": ns.include})),

    ("outcomes", "List course outcomes", """
        course_id int
    """, lambda ns: paginate(f"/courses/{ns.course_id}/outcomes")),

    ("progress", "Check an async operation's progress", """
        progress_id int
    """, lambda ns: get(f"/progress/{ns.progress_id}")),
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="canvas_cli.py",
        description="Canvas LMS CLI",
        epilog="List commands paginate automatically; output is JSON.",
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")
    for name, description, spec, handler in COMMANDS:
        p = sub.add_parser(name, help=description, description=description)
        positionals, optionals = build_args(spec)
        for arg_name, opts in positionals:
            p.add_argument(arg_name, **opts)
        for flags, opts in optionals:
            p.add_argument(*flags, **opts)
        p.set_defaults(func=handler)
    return parser


def main() -> None:
    parser = build_parser()
    ns = parser.parse_args()
    if not getattr(ns, "func", None):
        parser.print_help()
        return

    try:
        data = ns.func(ns)
        print(data if isinstance(data, str) else json.dumps(data, indent=2))
    except CanvasHTTPError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
    except CanvasError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
