---
status: accepted
---

# A condition may cite one source, if it says why

The two-source rule is relaxed by exception rather than absolutely: a condition
may cite a single source when it carries a `single_source_reason` explaining
why. The schema enforces this — one source without a reason fails to load, and
a reason without a single source also fails, so the field cannot become a
standing exemption.

## Why

The rule exists so that no condition rests on a single **document**. Adenomyosis
has no second usable source — MedlinePlus mentions it only in link lists
pointing at copyrighted Mayo Clinic content; NICHD, CDC, the Office on Women's
Health and WHO have no page; NICE CKS covers it but its licence is not
satisfiable outside the UK.

Yet NHS names adenomyosis alongside endometriosis as a cause of heavy and
painful periods on three separate pages. It is a differential our own sources
insist on. Omitting it does not make the system safer — a differential missing a
condition the sources keep naming will attribute those symptoms to whatever else
is available, which here means endometriosis.

NHS covering it across three documents meets the rule's purpose while failing
its letter. Refusing to model a real differential on that technicality is its
own kind of error.

## Considered options

- **Keep the rule absolute.** Defensible, and "we could not author adenomyosis
  under our own evidence standard" is a strong sentence in a write-up. Rejected
  because the cost falls on the differential rather than on the paperwork.
- **Silently lower `min_length` to 1.** Rejected outright. The rule would erode
  to "two sources, usually", and nobody reading a condition would know which
  ones were corroborated.

## Consequences

**The exception is deliberately awkward.** It cannot be taken by omission — only
by writing an argument into the file that a reviewer reads. That is the point.

**Adenomyosis is the only condition with no corroborating source.** If NHS is
wrong about something in it, nothing catches it. This must be stated wherever
coverage is reported, alongside the existing silver-annotation caveat.

**Watch for a second exception.** One documented exception is a considered
judgement; three would mean the rule is not working and should be redesigned
rather than repeatedly excused.
