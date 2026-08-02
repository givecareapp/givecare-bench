# GiveCare Workpad

Multi-document Markdown store with an inspectable human/agent trail. The store
(`src/store.ts`) is the primitive: content-addressed revisions, an append-only
attributed ledger, and compare-and-swap saves with 3-way merge. The HTTP server
and the `workpad` CLI are adapters over it. Review links to the web surface, but
Flask does not own its auth, storage, or lifecycle.

## Store layout

Each document lives under `WORKPAD_DIR/<doc-id>/` (`doc-id` matches
`[a-z0-9][a-z0-9-]{0,63}`):

```text
<doc-id>/doc.md                      # readable Markdown projection
<doc-id>/activity.jsonl              # append-only human/agent saves and notes
<doc-id>/revisions/<sha>.md          # content-addressed snapshots
<doc-id>/archive/activity.<n>.jsonl  # rotated ledgers (checkpoint chain roots)
```

The ledger event and both revision snapshots are durable before the projection
is replaced; an interrupted save rematerializes from the ledgered revision, and
an unledgered projection fails closed. The hot path verifies the chain tail
only; full replay lives in `workpad fsck`. When the active ledger passes 1 MiB
it rotates into `archive/` behind a `checkpoint` event, so the ledger never
outgrows its read cap. A stale `base_sha` triggers a line-level 3-way merge
against the shared revision ancestry; only overlapping edits return `409`.
Writes are guarded by an in-process queue plus a cross-process lockfile. The
pre-multi-doc layout (`shared-workpad.md` at the data root) migrates
automatically on first access.

## CLI (agents and scripts)

On-host actors use the store directly — filesystem access is authority; no
HTTP, tokens, or cookies:

```bash
export WORKPAD_DIR=…/workpads WORKPAD_SEED_PATH=…/seed.md
workpad get                          # print the document (stderr: id @ sha)
echo "…" | workpad save --latest --note "why"   # attributed CAS save
workpad note --latest "a decision"   # trail note without editing
workpad log --limit 20               # newest-first activity
workpad docs                         # list documents in the store
workpad fsck | repair | compact | gc [--apply]  # maintenance
```

Actor identity comes from `--as id[:kind[:role]]` or `WORKPAD_ACTOR`
(default `cli:agent:editor`). Conflicting saves exit `3` with the current sha.
`--doc` targets a document other than `shared-workpad`; `--json` emits
machine-readable output.

## Web surfaces

- `/workpad/demo` — public, synthetic, browser-local editing and provenance.
- `/workpad` — private document after an invitation mints a separate, expiring,
  HttpOnly, path-scoped session cookie.
- `/workpad/invite/<token>` — confirm page only; redemption is a POST to
  `/workpad/api/invite/redeem` (single-use, rate-limited), so link prefetchers
  and mail scanners cannot burn an invitation.
- `/workpad/api/events` — session-gated SSE stream; the editor live-reloads
  when another actor (e.g. the CLI) saves, and merges instead when local edits
  are in flight.
- `/workpad/intake-ledger` — session-gated, read-only Hound intake chronology.
  The browser reaches only this Workpad page; the server makes one bounded
  `AF_UNIX` request to the fixed `HOUND_SOCKET` and never reads or writes the
  Workpad document, revision, activity, draft, or SSE stores for this route.
  Its Hound producer, policy, access ceiling, page size, and filter are fixed
  server configuration (`HOUND_LEDGER_*`), never browser input.
- `/workpad/health` — service-specific deployment probe.
- Trail → “Sign out of this workpad” — revoke the current server-side session
  and clear its cookie through the CSRF-protected logout API.

The private invitation file is mode `600` and separate from Review. Every
invitation requires `expires`, a token of at least 22 url-safe characters, and
can be redeemed once:

```text
token=<urlsafe22+> role=owner id=ali docs=shared-workpad expires=<ISO-8601>
token=<urlsafe22+> role=editor id=collaborator docs=shared-workpad expires=<ISO-8601>
token=<urlsafe22+> role=viewer id=observer docs=shared-workpad expires=<ISO-8601>
```

Raw session credentials are never written to disk. Their hashes, issuance,
expiry, and revocation events are kept in the mode-`600`
`WORKPAD_SESSIONS_PATH` JSONL file. Sessions expire after seven days or when
their invitation expires, whichever comes first. A torn trailing line in either
ledger is tolerated on read and quarantined by `workpad repair`; interior
corruption fails closed.

## Commands

```bash
pnpm install --frozen-lockfile
pnpm test
pnpm typecheck
pnpm build        # client bundle + dist/server.mjs + dist/cli.mjs
WORKPAD_PORT=3092 pnpm start
```

The editor uses TipTap, the same underlying editor family as Hubble.md. This
pilot intentionally supports a constrained Workpad dialect. Existing Wiki
files remain outside its write boundary: corpus testing showed rich
parse/serialize was not byte-preserving for the current wiki.

## Deployment

The built service is `dist/server.mjs` (node builds externalize npm packages —
run from this directory so `node_modules` resolves). Production runs it
separately from `review-ui` and routes only `review.givecareapp.com/workpad*`
to its port. That same service can later run as the private Helm/Open instance
with different `WORKPAD_DIR`, `WORKPAD_TOKENS_PATH`, and
`WORKPAD_SESSIONS_PATH` values.
