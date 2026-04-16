---
name: ai-spec
description: "Use when: reading, implementing, or aligning code with ai/*.md specification files. Guides the agent through the specification-driven workflow and ensures strict adherence to documented architecture and conventions."
---

# AI Specification Workflow

You are working in a **specification-driven project**. The `ai/` directory contains authoritative rules and design documents that MUST guide all implementation.

## Step 1: Read the specification first
Before proposing or implementing anything, read the relevant spec files from `ai/`:
- `ai/00_rules.md` — global AI behavior rules (highest priority)
- `ai/01_architecture.md` — project goals, tech stack, expected structure
- `ai/02_coding_style.md` — Python style, naming, logging rules
- `ai/03_spider_spec.md` — spider request/concurrency constraints
- `ai/04_data_schema.md` — unified data format definitions
- `ai/05_anti_blocking.md` — request strategy and rate limiting
- `ai/06_error_handling.md` — error handling and recovery patterns
- `ai/07_task_template.md` — template for new work items
- `ai/08_review.md` — self-check criteria before finishing
- `ai/10_target_sites.md` — target sites and scope (if present)
- `ai/11_pipeline_spec.md` — extraction pipeline stages (if present)
- `ai/99_current_state.md` — current project status and next steps

## Step 2: Plan before coding
- Explain what you understand from the spec
- Explain your implementation approach
- Identify any spec gaps or conflicts BEFORE writing code
- Separate concerns by spec stage (e.g., list extraction vs detail extraction)

## Step 3: Then implement
- Follow all documented constraints
- Preserve stage boundaries
- Do not invent fields, APIs, or selectors outside the spec
- Use modular functions aligned with spec structure

## Step 4: Self-check before finishing
- Validate against all relevant spec files
- Use the review checklist from `ai/08_review.md`
- Confirm no undocumented assumptions were made
- Verify stage isolation and error handling

## Strict prohibitions
- DO NOT invent architecture or fields outside the spec
- DO NOT skip planning
- DO NOT assume hidden APIs or page structures
- DO NOT mix spec stages (e.g., list + detail extraction)
- DO NOT drift outside current scope defined in `ai/*.md`

## When in doubt
Ask the user:
- What spec files or fields are undefined?
- Whether new fields should extend `ai/04_data_schema.md`
- What the current focus from `ai/99_current_state.md` tells us
- Anything that conflicts with or is missing from the spec
