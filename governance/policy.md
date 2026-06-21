# LIEM SYSTEM GOVERNANCE POLICY

## 1. Execution & Cost Governance
- **Maximum Cost per Run**: $2.00 USD
- **Maximum Token Usage per Prompt**: 120,000 tokens
- **Maximum Parallel Executions**: 4 parallel tasks
- **Alert Channel**: `#liem-alerts`

## 2. Security & Sandbox Compliance
- All code-writing and execution agents must run within sandbox environments.
- Direct root or administrator operations inside production targets are strictly prohibited.
- Telemetry trackers must scrub credentials and sensitive inputs.

## 3. Human Approval (HITL) Gateways
- Double-human sign-off is required for all production deployments.
- Database ALTER and migration commands require SRE and DBA validation.
