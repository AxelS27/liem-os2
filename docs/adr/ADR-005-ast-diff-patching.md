# Architecture Decision Record: ADR-005 - AST-based Chunking, Search-and-Replace Blocks, and AST Node Injections

## Context & Problem
Rehydrating entire code files into leaf developer agents causes token window explosion and high costs. Additionally, relying on LLMs to generate line-number-based Git `.patch` files frequently leads to hallucinations and merge/patch rejects, causing infinite failure loops.

## Decision
- **Forbid Git-style Patches**: Standard Git `.patch` diffs and `git apply` operations are deprecated and prohibited.
- **Search-and-Replace Blocks**: Leaf developer agents must specify changes using exact substring-matched Search-and-Replace blocks (Schema A).
- **AST Node ID Injections**: Alternatively, agents can target specific code objects (classes, functions, methods) by referencing their unique AST Node ID (e.g., `module::function`). The Context Compressor will directly replace the AST node body with the new implementation (Schema B), bypassing line numbers entirely.

## Consequences
- Eliminates line-number hallucination errors.
- Keeps prompt context windows small for developer agents.
- Drastically reduces token usage and improves execution reliability.
- Requires robust AST parsing engines in the execution environment.
