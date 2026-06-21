# Architecture Decision Record: ADR-006 - LLM-Friendly Search-and-Replace Blocks

## Context & Problem
LLMs frequently hallucinate line offsets and numbers when generating standard Git `.patch` files, leading to merge failures and syntax errors.

## Decision
All developer agents must output modifications using distinct Search-and-Replace code blocks. The block specifies the exact existing code segment (as substring) and the replacement segment. The Context Compressor executes a search-and-replace algorithm to apply changes.

## Consequences
- Eliminates line number hallucinations.
- Drastically improves code integration success rates.
- Requires exact substring matches, meaning whitespace and formatting must be parsed carefully.
