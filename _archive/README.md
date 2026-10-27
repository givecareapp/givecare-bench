# Previous benchmark

`5.8.0/` preserves every public tracked file from source revision
`22552fed3171ad3a324ccf47fe1d092f863ba29d`, with its contents and executable modes
unchanged. It includes the implementation, scenarios, checks, tests, documentation,
package configuration, lockfile, and published artifacts. The version name alone
does not identify all development changes; the full revision is authoritative.

Before archiving, the offline gate passed: Ruff, strict turn indices, 585 of 585
saved exemplars, and 508 public tests. Root `scripts/check.sh` runs that same gate
from the archived project. Fresh-checkout checks may need the locked dependencies
installed by `uv`; the benchmark checks themselves make no paid provider calls.

The Git repository, root hooks, license, ignore rules, Python version, module
contract, and published `data/` artifacts remain at their original paths. Their
tracked versions also appear in this snapshot. Secrets, environments, run logs,
and the separate private repository were not copied into the public archive.
Local ignored caches within moved project directories remain ignored.

Private instructions from this revision are preserved separately at
`private/_archive/5.8.0/AGENTS.md`; root agent instructions describe the rebuild.

Archived documentation describes historical paths and behavior. Its private
overlay and run evidence are not relocated here. For hash-bound historical replay,
use the exact source revision recorded by the run rather than treating this
directory move as a new result.

The archive is reference material, not an active dependency or an independent
validation set. Bring back only the engineering needed for a verified new slice.
Do not edit the snapshot to satisfy new requirements.
