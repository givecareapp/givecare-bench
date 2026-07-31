# GiveCare Workpad

Standalone TypeScript service for a readable, editable Markdown document with
an inspectable human/agent trail. Review links to it, but Flask does not own its
auth, storage, or lifecycle.

## Surfaces

- `/workpad/demo` — public, synthetic, browser-local editing and provenance.
- `/workpad` — private document after a single-use invitation mints a separate,
  expiring, HttpOnly, path-scoped session cookie.
- `/workpad/health` — service-specific deployment probe.
- Trail → “Sign out of this workpad” — revoke the current server-side session
  and clear its cookie through the CSRF-protected logout API.

The private invitation file is mode `600` and separate from Review. Every
invitation requires `expires` and can be redeemed once:

```text
token=<urlsafe> role=owner id=ali docs=shared-workpad expires=<ISO-8601>
token=<urlsafe> role=editor id=collaborator docs=shared-workpad expires=<ISO-8601>
token=<urlsafe> role=viewer id=observer docs=shared-workpad expires=<ISO-8601>
```

Raw session credentials are never written to disk. Their hashes, issuance,
expiry, and revocation events are kept in the mode-`600`
`WORKPAD_SESSIONS_PATH` JSONL file. Sessions expire after seven days or when
their invitation expires, whichever comes first. Deleting or revoking an
invitation does not restore a consumed invitation.

Every edit carries a `base_sha`. A stale editor receives `409` instead of
overwriting. Current Markdown, content-addressed revision snapshots, and the
append-only activity ledger live beneath `WORKPAD_DIR`. The activity event and
both revision snapshots are durable before the readable Markdown projection is
replaced; startup/load recovery rematerializes an interrupted projection from
that ledgered revision.

## Commands

```bash
pnpm install --frozen-lockfile
pnpm test
pnpm typecheck
pnpm build
WORKPAD_PORT=3092 pnpm start
```

The editor uses TipTap, the same underlying editor family as Hubble.md. This
pilot intentionally supports a constrained Workpad dialect. Existing Wiki
files remain outside its write boundary: corpus testing showed rich
parse/serialize was not byte-preserving for the current wiki.

## Deployment

The built service is `dist/server.mjs`. Production runs it separately from
`review-ui` and routes only `review.givecareapp.com/workpad*` to its port.
That same service can later run as the private Helm/Open instance with
different `WORKPAD_DIR`, `WORKPAD_TOKENS_PATH`, and
`WORKPAD_SESSIONS_PATH` values.
