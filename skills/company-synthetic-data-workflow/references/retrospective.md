# Retrospective / Skill Reconciliation

The closing step of every run. Reconcile **what actually happened** against **what the skill
says**, then feed the gaps back into the skill so it improves with each client. Keep it
lightweight — a short report plus concrete edits, not a second project.

## When

After analytics are delivered and validated, before considering the engagement done. Run it
while the full session context is still available.

## What to check

Scan the session against the skill and answer, briefly and honestly:

1. **Steps skipped or shortcut.** Which required workflow steps were not done, or done
   partially? (e.g. presented a compressed plan instead of the explicit monthly table.)
2. **Reference docs not read.** The skill names docs to read (`metric-definitions.md`,
   `channel-mix-benchmarks.md`, `data-issues-menu.md`, `generator-contract.md`,
   `stage-cleaning.md`, the schema indexes). Which were actually opened vs inferred from an
   existing company's code? Inferring instead of reading is itself a finding.
3. **Deviations from the workflow.** Where did the run diverge from the documented sequence
   or gates, and was the divergence justified?
4. **Things done that aren't in the skill but should be.** New techniques, modeling rules, or
   source systems introduced ad hoc that future runs would benefit from. These are candidate
   skill edits.
5. **Estimates vs realized.** Where did pre-generation estimates (row volumes, metrics) drift
   from what was generated, and why? Tighten the guidance if the miss was systematic.
6. **Corrections prompted by the user.** Anything the user had to catch that the skill should
   have caught on its own — those are the highest-value codifications.

## Output

- A short retrospective written back to the user (the six points above, only where there's
  something to say).
- **Concrete skill edits**: apply the clear wins directly (new reference note, a tightened
  step, a new check), and list the larger ones as proposals. A finding that produces no
  change to the skill, a reference doc, or `validate_raw` was not really actioned.
- Update project memory with anything durable.

## Guardrails

- This is reconciliation, not a rewrite. Prefer the smallest edit that prevents the gap from
  recurring.
- Codify **general** principles, not client-specific facts (those go in the setup yaml).
- If nothing meaningful diverged, say so in one line and stop — don't manufacture findings.
