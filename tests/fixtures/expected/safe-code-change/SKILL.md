---
name: safe-code-change
description: Inspect existing project context before editing and verify changes in increasing scope. Use when Changing code in an existing project. Do not use when Only answering a read-only question.
---

# Safe Code Change

## Principles

- Inspect before editing
- Reuse existing implementation before adding files

## Workflow

1. Inspect the README, architecture, and current implementation
2. Make the smallest relevant change
3. Run focused checks, then the full test suite and lint

## Constraints

- Run focused tests before full verification
- Do not report completion while required checks fail

## Do not use when

- Only answering a read-only question

## Source references

- `<DOCUMENT_ID>` — Direct instruction to inspect existing project context
  > Before changing code, inspect the README, architecture, and existing implementation.
- `<DOCUMENT_ID>` — Direct instruction to verify changes before completion
  > Then run the full test suite and lint before reporting completion.
