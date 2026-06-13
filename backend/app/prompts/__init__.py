"""
Prompt registry for RecruitAI.

Why prompts live in files (and not in Python code)
--------------------------------------------------
Prompts are part of the product surface — they affect output quality more
than most lines of code, and they need to be reviewable, diffable and
testable independently. Treating them as content (Markdown files) instead
of constants gives us:

* **Diff-friendly reviews** — a PR that tweaks 3 lines of a prompt shows
  exactly those 3 lines, not a wall of f-string noise.
* **Prompt evals** — ``backend/evals/`` can load the same prompt file the
  runtime uses, so a regression in extraction quality is detectable.
* **Version pinning** — when we A/B-test a new wording we save the
  previous file with a suffix (``extract_cv.v1.md``) and the loader
  routes by an env var. No code change required.
* **Cacheable for cloud LLMs** — Anthropic / Gemini / OpenAI prompt
  caching kicks in only when the *prefix* of the prompt is byte-identical
  across requests. A stable file is the easiest way to guarantee that.

Template syntax
---------------
We use :class:`string.Template` (``$variable``) instead of ``.format()``
or Jinja2 because prompts contain JSON examples with literal ``{`` and
``}``. ``string.Template`` ignores those characters entirely.

Usage
-----
    from app.prompts import render

    prompt = render(
        "extract_cv",
        cv_text=sanitized_text,
    )

Files are read once on first use and cached in-process.
"""
from __future__ import annotations

import logging
from pathlib import Path
from string import Template
from typing import Any

logger = logging.getLogger(__name__)

_PROMPT_DIR = Path(__file__).parent
_CACHE: dict[str, Template] = {}


def _load(name: str) -> Template:
    """Return a :class:`string.Template` for ``<name>.md``.

    Cached after first read. Missing files raise ``FileNotFoundError``
    with a path that points to where the prompt should live, so the
    error message is actionable.
    """
    cached = _CACHE.get(name)
    if cached is not None:
        return cached
    path = _PROMPT_DIR / f"{name}.md"
    if not path.is_file():
        raise FileNotFoundError(
            f"Prompt '{name}' not found at {path}. "
            "Add the file under backend/app/prompts/ or fix the name."
        )
    text = path.read_text(encoding="utf-8")
    tmpl = Template(text)
    _CACHE[name] = tmpl
    return tmpl


def render(name: str, **variables: Any) -> str:
    """Render the prompt called ``name`` with the given ``$variable`` substitutions.

    Missing variables raise :class:`KeyError` — never produce a prompt
    with literal ``$missing_var`` text that a model would faithfully echo
    back as if it were content.
    """
    return _load(name).substitute(variables)


def reload() -> None:
    """Clear the in-process cache. Useful in tests and dev hot-reload."""
    _CACHE.clear()


__all__ = ["render", "reload"]
