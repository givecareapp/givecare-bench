# InvisibleBench

InvisibleBench is being rebuilt around multi-turn caregiver support: whether an
assistant provides useful help while respecting caregiver capacity, both people's
agency, the availability of support, and danger to either person.

The previous implementation is preserved in [_archive/5.8.0](_archive/5.8.0/README.md).
See the [archive record](_archive/README.md) for its source revision and verification.
There is no replacement implementation or new benchmark result yet.

## Rebuild boundary

- Design new cases from caregiver evidence. Capacity, agency, access, and safety
  are proposed coverage domains, not validated scales.
- Keep multi-turn evaluation. Use matched conditions to test whether relevant
  history and changed facts alter the response appropriately.
- Report Safety and Care separately. A lack of violations does not establish
  useful help, clinical validity, or caregiver benefit.
- Start with one matched family and an independently assessed comparison.
  Development cases are not independent validation evidence.
- Bring archived engineering into the active project only when a concrete need
  and verification justify it. Do not import the old corpus or rubric by default.
- Reuse Inspect before building execution machinery. Paid inference requires a
  saved plan and an explicitly approved ceiling.

## Working tree

```text
_archive/5.8.0/   frozen previous public project
scripts/check.sh historical verification entry point
data/            unchanged published artifacts for existing consumers
private/         separate, ignored private repository
results/         ignored historical run evidence
```

Repository history, local credentials, and private evidence remain in place.
Archiving does not remove prior exposure to benchmark content. New independent
validation requires separately authored, withheld case families.

## Verify the archive

```bash
scripts/check.sh
```

This runs the archived project's unchanged offline gate. It verifies historical
engineering, not the proposed measurement design. Historical commands and
dependencies live in the archive; the repository root no longer installs the
old `bench` CLI. Use the original recorded Git revision when replay requires
historical source identity.

The published artifacts under `data/` remain the previous release. This rebuild
has not been published. Licensed under [MIT](LICENSE).
