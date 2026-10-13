---
name: markitdown-cli
description: "Convert documents to Markdown using Microsoft's MarkItDown library: PDF, DOCX, PPTX, XLSX, HTML, CSV, JSON, XML, YAML, EPUB, ZIP, Outlook .msg, Jupyter notebooks, images (with optional local OCR), and audio. Use when asked to convert, extract text from, or read a document/attachment/slidesheet/spreadsheet into Markdown or plain text for analysis, archiving, or LLM consumption."
metadata:
  author: pi-user
  version: "2.0"
---

# markitdown-cli

Convert files to Markdown with Microsoft's [MarkItDown](https://github.com/microsoft/markitdown).
Everything runs out of a virtualenv inside this skill — no system packages needed.

## Usage

```bash
CLI=~/.gemini/config/skills/markitdown-cli/scripts/markitdown_cli.py
python3 $CLI <input(s)> [options]
```

Set `$CLI` in the same command, since shell variables don't persist between calls.
The script re-execs itself into the skill's `.venv`, so plain `python3` is all you need.

## Setup (already done)

The skill ships a ready virtualenv at `.venv/`. To rebuild or extend it:

```bash
cd ~/.gemini/config/skills/markitdown-cli
python3 -m venv .venv
.venv/bin/pip install 'markitdown[all]' openai
```

`openai` is required for OCR and is **not** included in the `markitdown[all]`
extra, so install it explicitly.

## Supported inputs

| Category | Extensions |
|----------|------------|
| Documents | `pdf`, `docx`, `pptx`, `xlsx`, `xls`, `epub`, `rtf`*, `msg` (Outlook) |
| Web      | `html`, `htm` |
| Data     | `csv`, `tsv`, `json`, `jsonl`, `xml`, `yaml`, `yml` |
| Text     | `txt`, `md`, `markdown` |
| Notebook | `ipynb` |
| Archive  | `zip` (converts each member) |
| Images   | `png`, `jpg`, `jpeg` (metadata, plus OCR with `--ocr`) |
| Audio    | `mp3`, `wav`, `m4a`, `mp4` (metadata only, no transcription) |
| URLs     | YouTube, Wikipedia, RSS, Bing SERP — pass the URL as the input |

\* `rtf` is only handled if it is actually plain text; real RTF is not converted.

**Legacy binary `.doc`, `.ppt`, `.xls` from old Office are not supported.** They
are skipped during batch runs. Convert them first (LibreOffice, or Word "Save As"
to `.docx`/`.pptx`) — passing a legacy file to a single-file conversion can emit
raw binary-looking text rather than failing cleanly.

Run `python3 $CLI --list-formats` to print the authoritative list from the
installed library, and `--doctor` to check the environment.

## Converting

```bash
# One file to stdout
python3 $CLI report.pdf

# One file to a specific name
python3 $CLI report.pdf -o report.md

# Several files into a directory
python3 $CLI a.pdf b.docx c.pptx -o ./markdown/

# A whole tree, preserving subdirectory structure
python3 $CLI ./papers/ -r -o ./markdown/

# From stdin (content is sniffed; give a hint if it matters)
cat page.html | python3 $CLI -i - -o page.md
cat scan.dat | python3 $CLI -i - --stdin-filename .pdf -o scan.md
```

In a batch run, unrecognised extensions are skipped and reported with `-v`.
Two inputs sharing a stem (`notes.pdf` and `notes.docx`) get `notes.md` and
`notes-2.md` rather than overwriting each other.

## OCR (local, opt-in)

Scanned pages and images have no text layer, so OCR is needed. This skill uses a
**vision model served on your own machine** — there is no tesseract or other
system package, and nothing is sent to a hosted API unless you point it at one.

Pick whichever local server you already run; they all speak the same API.

**Ollama** (simplest):
```bash
ollama serve
ollama pull qwen2.5vl          # or: llava, minicpm-v, gemma3
python3 $CLI scan.png --ocr
```

**llama.cpp / LM Studio / vLLM**:
```bash
python3 $CLI scan.png --ocr \
  --ocr-base-url http://localhost:8080/v1 \
  --ocr-model gemma-3-4b-it
```

Good OCR-capable vision models: `qwen2.5vl`, `dots.ocr`, `got-ocr2.0`,
`PaddleOCR-VL`, `minicpm-v`, `llava`. For dense tables or handwriting, an
OCR-specialised model beats a general captioner.

Verify the wiring before a long batch job:
```bash
python3 $CLI --doctor --ocr --ocr-base-url http://localhost:8080/v1
```
It reports whether the endpoint is reachable and which models it serves.

| Option | Purpose |
|---|---|
| `--ocr` | enable OCR via the local vision endpoint |
| `--ocr-base-url` | endpoint (default `http://localhost:11434/v1`, Ollama) |
| `--ocr-model` | model name (default `llava`) |
| `--llm-prompt` | override the prompt; defaults to a transcription instruction |
| `--no-metadata` | omit the `title` frontmatter block |

Defaults can live in `.env` next to the script:
```
MARKITDOWN_OCR_BASE_URL=http://localhost:8080/v1
MARKITDOWN_OCR_MODEL=qwen2.5vl
```

OCR applies to images and image-only PDFs. A PDF with a real text layer does not
need it — text is extracted directly and is faster and more accurate.

## Notes

- Output goes to stdout unless `-o` is given, so it pipes cleanly into `jq` or a file.
- Exit status is non-zero if any file fails to convert.
- `--list-formats` and `--doctor` exit without needing an input file.
- `exiftool` (optional) enriches image metadata; without it, images yield only
  the OCR/description text.
- Audio conversion produces metadata only. Audio transcription is not supported.

## Tests

```bash
python3 ~/.gemini/config/skills/markitdown-cli/scripts/test_markitdown_cli.py
```

27 offline tests, no network. They cover conversions, batch/collision handling,
frontmatter, and the full OCR path against a stub local vision server.
