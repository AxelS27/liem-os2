# LIEM BOOTSTRAP: REGISTRY LOADER

**Objective**: Cold-starts and validates the agent skill and capability registries.
**Steps**:
1. Scan `agents/` directories and read frontmatter for all `.md` skills.
2. Cross-reference files with `registry/agents.yaml`.
3. Verify that all declared capabilities exist in `registry/capabilities.yaml`.
4. Report any missing capability mappings or broken paths to `telemetry/startup.log`.
