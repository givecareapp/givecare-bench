# Security Policy

## Supported versions

The current benchmark contract is **2.1.0** (per
`benchmark/benchmark_card.json` and `pyproject.toml`). Security fixes
land on `main` and are published as a new patch or minor version.

| Version | Supported |
|---------|-----------|
| 2.1.x   | Yes       |
| < 2.1   | No        |

## Reporting a vulnerability

Please do **not** open a public GitHub issue for security concerns.

Preferred channel: [GitHub's private security advisory form](https://github.com/givecareapp/givecare-bench/security/advisories/new).

Alternative: email `ali@scty.org`. Please include:
- A description of the issue and its impact
- Steps to reproduce (scenario id, model, transcript, run id if applicable)
- Your disclosure timeline preference

## What counts as a security issue

- **Scorer manipulation** — adversarial prompts that cause a scorer to
  systematically misjudge a response class.
- **Prompt injection against judges** — scenario content that escapes into
  the judge's instruction context.
- **Leaked private material** — if any gitignored prompt, rule file, or
  Convex key shows up in a published artifact (`data/leaderboard/`,
  released Convex payload, test fixtures, git history).
- **Credential exposure** — hardcoded keys, tokens, or deployment IDs in
  committed code or CI logs.
- **Supply-chain issues** — compromised dependencies, typosquatting,
  dependency confusion against `invisiblebench`.

Scoring errors that aren't adversarial in origin are bugs, not security
issues — report those in a regular issue.

## Response expectations

- Acknowledgement within **7 days** of first contact.
- A status update (fix planned / no-fix / need more info) within
  **30 days**.
- Credit in the fix commit and release notes if you'd like, or anonymous
  if you prefer.

We do not run a bug bounty program.
