---
status: accepted
---

# evidence.csv is generated from approved batches, not authored

Evidence rows are authored in numbered batch files and `knowledge/evidence.csv`
is generated from them by `make evidence`. A batch contributes rows only when it
carries `approved: true`; drafts are parsed and validated but excluded. The file
is tracked in git despite being generated, because it is what the system loads.

## Consequences

**The review gate is enforced by code rather than by memory.** Drafting rows
ahead of review is safe by construction — an unread batch cannot reach the
knowledge base whatever anyone forgets. This is what makes it possible to
prepare work for review without risking unreviewed clinical content.

**The artifact a human reads and the artifact the system loads cannot drift.**
The batch file is readable — one block per row, the quote on its own lines, a
note explaining the judgement. The CSV is machine input. Generating one from the
other removes the possibility of them disagreeing.

**Never hand-edit the CSV.** Every source quote contains commas and often nested
quotation marks; one stray character silently changes a clinical claim or shifts
every column right. Edits go to the batch file.

The build is deterministic — rows sorted, so re-running is byte-identical and a
diff only ever shows a real change.
