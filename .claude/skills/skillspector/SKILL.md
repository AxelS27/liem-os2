---
name: skillspector
description: >
  Scan AI agent skills, plugins, or codebases for security vulnerabilities,
  malicious patterns, prompt injection, and excessive privilege using NVIDIA's SkillSpector.
---

# NVIDIA SkillSpector

A security scanner for AI agent skills to evaluate security and integrity before installation.

## Rules & Trigger Protocols
- Use this skill when the user asks to "scan skills", "audit skill security", or check if a third-party plugin/skill is safe to run.
- Always check if the `skillspector` CLI is available. If not, fallback to using Docker.

## Usage Commands

### Standard Static Scan (Recommended)
Runs fast static analysis checking for taint tracking, dangerous code patterns, and supply chain issues:
```bash
skillspector scan <target_directory_or_file> --no-llm
```

### Docker-based Scan (If CLI not installed)
```bash
docker run --rm -v "${PWD}:/scan" skillspector scan <target_directory_or_file> --no-llm
```

### LLM-backed Semantic Scan (For deep analysis)
Evaluate intent, filter false positives, and get detailed descriptions (requires provider API key):
```bash
skillspector scan <target_directory_or_file> --provider <provider_name>
```

### Formatted Reports
Export report to Markdown or JSON for documentation/audits:
```bash
skillspector scan <target> --format markdown --output security_report.md
```
