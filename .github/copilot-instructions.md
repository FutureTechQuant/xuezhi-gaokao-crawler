# Workspace Instructions (AI-Controlled Crawler Project)

This workspace is an AI-driven Python crawler project.  
All agent behavior MUST follow the rules defined in the `/ai` directory.

---

# 🔴 SOURCE OF TRUTH (Highest Priority)

The `ai/` directory is the SINGLE SOURCE OF TRUTH.

You MUST:

- Always follow `ai/00_rules.md` as the highest priority
- Treat all `ai/*.md` files as strict constraints, not suggestions
- NEVER override or ignore rules defined in `/ai`
- NEVER invent architecture, fields, selectors, endpoints, or parsing logic outside `/ai` definitions

If there is any conflict:
> `/ai/*.md` overrides everything else

---

# 📚 Canonical Documentation (MUST READ BEFORE ACTION)

Before writing code or modifying documentation, you MUST read relevant files in `ai/`:

- `ai/00_rules.md` — global AI behavior rules
- `ai/01_architecture.md` — project goals, structure, and engineering boundaries
- `ai/02_coding_style.md` — Python style, naming, logging, and structure rules
- `ai/03_spider_spec.md` — spider requirements for CHSI / XZ
- `ai/04_data_schema.md` — unified data schema definitions
- `ai/05_anti_blocking.md` — anti-blocking strategy
- `ai/06_error_handling.md` — error handling and recovery rules
- `ai/07_task_template.md` — task template
- `ai/08_review.md` — review checklist
- `ai/10_target_sites.md` — target sites, entry pages, and page characteristics
- `ai/11_pipeline_spec.md` — four-stage extraction pipeline
- `ai/99_current_state.md` — current project focus and next steps

You MUST only read the files relevant to the current task, but you MUST align with all higher-priority rules.

---

# 🧠 REQUIRED WORKFLOW (MANDATORY)

For ANY development task, you MUST follow this workflow:

### Step 1 — Understand Context
- Read the relevant `ai/*.md` files first
- Identify site scope, schema scope, and pipeline stage
- Identify missing samples or undefined fields before coding

### Step 2 — Plan First
- Explain task understanding
- Explain implementation approach
- Explicitly separate:
  - Stage 1 list extraction
  - Stage 2 detail extraction
  - Stage 3 normalization
  - Stage 4 GitHub Actions automation

### Step 3 — Then Implement
- Write code only after planning
- Follow architecture, coding style, schema, and spider constraints
- Keep list parsing, detail parsing, and file writing separated
- Prefer modular functions and reusable parsers

### Step 4 — Self-Check
- Validate against:
  - `ai/01_architecture.md`
  - `ai/02_coding_style.md`
  - `ai/03_spider_spec.md`
  - `ai/04_data_schema.md`
  - `ai/11_pipeline_spec.md`
  - `ai/08_review.md`

---

# 🕷️ Project Overview

This project contains two target sites:

- CHSI（阳光高考）
  - 专业信息
  - 院校信息
- XZ（学职平台）
  - 专业信息
  - 职业信息

Core engineering goals:

- Site-isolated implementation
- Stage-isolated extraction flow
- Structured JSON output
- Stable GitHub Actions execution
- Automatic sync from `output/` to `data/`
- Partial recovery when failures occur

---

# 🧱 Expected Architecture

The project architecture is defined by `ai/01_architecture.md`.

Recommended structure:

```text
project/
  scripts/
    chsi/
      majors.py
      schools.py
    xz/
      majors.py
      careers.py
  parsers/
    chsi/
    xz/
  data/
    chsi-zyk/
    chsi-schools/
    xz-major/
    xz-career/
  output/
  .github/workflows/
```

Rules:

- CHSI and XZ must remain isolated by directory and script responsibility
- Page access, field extraction, detail parsing, and file writing must remain separated
- Do not create new folders or architectural layers unless required by the current `ai/*.md` rules or explicitly requested

---

# ⚙️ Technical Conventions

You MUST align with the current project stack:

- Python 3.12
- Playwright as the primary browser automation tool
- Parsing tools may include:
  - `re`
  - `lxml`
  - `BeautifulSoup`
- Output format: JSON
- Automation runtime: GitHub Actions

Do NOT default to `aiohttp`, SQLite, or MongoDB unless the task explicitly requires them.

---

# 🧩 Spider Implementation Constraints

From `ai/03_spider_spec.md` and `ai/11_pipeline_spec.md`:

Every spider must define:

- `base_url`
- `headers`
- request frequency
- parsing rules

Must include:

- random User-Agent
- timeout
- retry logic

Concurrency rules:

- max concurrency = 5
- request interval = 1 second

Mandatory extraction model:

### Stage 1 — List Extraction
- Extract only base fields, detail URLs, related URLs, page context, and business keys
- Do NOT parse rich detail content here

### Stage 2 — Detail Extraction
- Parse detail fields into structured objects
- Handle missing fields explicitly
- `raw_text` may exist only as fallback, not as the only output

### Stage 3 — Normalization
- Merge Stage 1 and Stage 2 results
- Output:
  - `all.json`
  - `xxx-flat.json`
  - `meta.json`
  - optional `xxx.partial.json`

### Stage 4 — Automation
- Install dependencies
- Install Playwright browsers
- Execute scripts
- Generate `output/`
- Sync `output/` to `data/`
- Commit and push only when files changed
- Upload artifact for debugging

You MUST NOT:
- skip Stage 1
- mix Stage 1 and Stage 2 logic
- omit source URLs
- generate files only in Actions without syncing them back

---

# 🌐 Site-Specific Scope

You MUST stay inside the site scope defined in `ai/10_target_sites.md`.

## CHSI
Current supported entities:
- Major
- School

Known characteristics:
- dynamic list pages
- filters and pagination
- multi-page school detail structure
- Playwright-first implementation

## XZ
Current supported entities:
- major
- career

Known characteristics:
- list pages with filters/search/pagination
- major detail page with four tabs:
  - basic_info
  - universities
  - courses
  - graduated_development

If a page structure is not confirmed by existing samples, do NOT invent parsing logic.

---

# 🗂️ Data Schema Rules

All output fields MUST follow `ai/04_data_schema.md`.

Current unified schema includes:
- CHSI Major
- CHSI School
- XZ major

Rules:
- Keep field names aligned with schema definitions
- Preserve source URL
- Preserve crawl time
- Preserve business keys such as `specId` and `schId`
- Use `raw_text` only as fallback
- Do not add unofficial fields unless explicitly requested

If the required field is not yet defined in `ai/04_data_schema.md`, ask first or clearly state that the schema must be extended.

---

# 🛡️ Anti-Blocking & Reliability

You MUST follow `ai/05_anti_blocking.md` and `ai/06_error_handling.md`.

Required anti-blocking behavior:
- use stable browser behavior and common UA
- use reasonable timeout
- avoid fixed sleep as the only waiting mechanism
- prefer selector + text + loading-state checks
- reduce frequency when blocked
- keep retry intervals reasonable

Required reliability behavior:
- catch page load failures
- catch selector failures
- catch missing field situations
- catch file writing failures
- preserve partial outputs when possible

If risk is detected, such as:
- 403
- 429
- blank page
- stale table
- invalid selector

You MUST explicitly mention the risk and adjust the strategy instead of blindly continuing.

---

# 📝 Coding Rules

From `ai/02_coding_style.md`:

- Use Python 3.12 syntax
- Use type hints
- Public functions must have docstrings
- One function should do one thing when possible
- Complex parsing logic must be split into independent functions

Naming:
- variables/functions: `snake_case`
- classes: `PascalCase`
- constants: `UPPER_CASE`

Logging:
- use `logging`
- do not use scattered `print` as formal logging
- logs should include stage, filter context, URL, and exception info
- long-running tasks must output progress logs

Structure:
- separate page access, parsing, normalization, and file writing
- list page functions must not directly perform detail-page structuring
- centralize file-writing logic

---

# ✅ Review Standard

Before finishing any implementation, self-check against `ai/08_review.md`:

- Is list parsing clearly separated from detail parsing?
- Does it fully cover the intended CHSI / XZ target scope?
- Are source URL, crawl time, and business keys preserved?
- Does it support partial output and error recovery?
- Can it run in GitHub Actions directly?
- Will it sync `output/` to `data/` and commit/push correctly?
- Are there obvious anti-blocking or unstable wait-condition risks?

---

# 🚫 STRICT PROHIBITIONS

DO NOT:

- invent APIs, endpoints, selectors, fields, or schemas
- assume hidden JSON APIs exist
- skip planning and jump directly to code
- mix list extraction and detail extraction into one uncontrolled procedure
- ignore partial output requirements
- break GitHub Actions compatibility
- simplify site-specific logic into generic templates if the project docs define a concrete structure
- drift outside the current project scope defined in `ai/*.md`

---

# ❓ When to Ask for Clarification

Ask first if any of the following is unclear:

- target page or entity scope
- missing schema fields
- missing HTML samples
- unclear business key
- unclear pagination behavior
- whether a new field should extend `ai/04_data_schema.md`
- whether a new page belongs to CHSI Major / School / XZ major / XZ career

If samples are incomplete, say so explicitly before proposing parsing logic.

---

# 📌 Notes

- This project is specification-driven, not free-form
- `ai/99_current_state.md` defines the current working focus
- Current work priority includes CHSI Major, CHSI School, and XZ major alignment
- XZ career may still require further schema convergence before full implementation
- Prefer conservative, verifiable parsing over speculative completeness

---

# ✅ FINAL PRINCIPLE

You are NOT a free-form coding assistant.

You are a controlled crawler engineer working under strict project documentation.

Follow the documented system, preserve stage boundaries, and do not improvise outside the defined scope.