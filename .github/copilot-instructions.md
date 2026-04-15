# Workspace Instructions

This project is a Python-based web crawler framework defined by the `ai/` documentation files. Use these instructions for all agent work unless a more specific file-level instruction exists.

## What this workspace is about
- A scraper/crawler project for Chinese gaokao-related data.
- Key design goals: decoupled, extensible, retryable.
- Expected architecture:
  - `spiders/`
  - `parsers/`
  - `pipelines/`
  - `storage/`
  - `utils/`
  - `config/`
- Data flow: request → parse → extract → clean → store.

## Primary documentation sources
Refer to these docs first; they are the project’s authoritative conventions.
- `ai/01_architecture.md` — architecture and technology choices.
- `ai/02_coding_style.md` — Python style, typing, logging, exception rules.
- `ai/03_spider_spec.md` — spider/requesting behavior and concurrency.
- `ai/99_current_state.md` — current status and next actions.

## Agent behavior and coding priorities
- Use Python 3.11 conventions.
- Prefer `aiohttp` for async HTTP requests.
- Use `BeautifulSoup` or `lxml` for HTML parsing.
- Persist data using `SQLite` or `MongoDB` depending on user preference.
- Keep functions small: ideally ≤ 50 lines.
- Use `snake_case` for functions/variables and `PascalCase` for class names.
- Add docstrings for all functions.
- Use `logging` for operational messages.
- Handle request, parse, and data exceptions explicitly.

## Spider implementation rules
- Every spider should define:
  - `base_url`
  - `headers`
  - request frequency
  - parsing rules
- Use random User-Agent headers.
- Include timeouts and retry logic.
- Concurrency limits:
  - max concurrent requests = 5
  - inter-request interval = 1 second

## When to ask for clarification
If the workspace has no source files or missing implementation details, ask the user for:
- the actual source folder or code layout
- preferred storage backend (`SQLite` vs `MongoDB`)
- specific target sites or spider requirements
- build/test commands if available

## Notes
- No existing `.github/` agent customization or README was present when bootstrapping this file.
- No Python source files were found in the workspace root at the time of creation.
