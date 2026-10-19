## Setup (already done)

The skill ships a ready virtualenv at `.venv/`. To rebuild or extend it:

```bash
cd ~/.gemini/config/skills/markitdown-cli
python3 -m venv .venv
.venv/bin/pip install 'markitdown[all]' openai
```

`openai` is required for OCR and is **not** included in the `markitdown[all]`
extra, so install it explicitly.
