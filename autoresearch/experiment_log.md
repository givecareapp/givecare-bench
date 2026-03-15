# Experiment Log — Campaign: mira-ib-mar11

Campaign branch at run time: `autoresearch/mira-ib-mar11` (now merged into `main`)

## Infrastructure Fixes (Pre-Campaign)

### Fix 1: playground:simulateInbound + getLastOutbound (2026-03-12 01:03 UTC)
- **Problem**: Both functions were stubs (logging only, returning null). All benchmark runs returned "(no response)" for every turn.
- **Fix**: Implemented real public Convex actions in `playground.ts` — `simulateInbound` calls `ingestInbound` + schedules `processInboundTurn`; `getLastOutbound` reads from `turnRuns.replyText` (not `messages` table which requires Twilio success).
- **Commit**: `1c7bbab`

### Fix 2: Bootstrap "OK" consent re-trigger (2026-03-12 01:42 UTC)
- **Problem**: Bootstrap step 5 sends "OK" for timezone confirmation. "OK" matches `CONSENT_GRANT_PATTERNS` → `processInboundTurn` re-triggered welcome message → phone looped back to name/situation step → all scenario turns received "What's your zip code?" instead of Mira.
- **Root cause in code**: `process.ts` line 190 checked `consentIntent === 'granted'` instead of tracking whether consent was just granted this turn. Applies even when user was already opted in.
- **Fix 1 (production)**: Added `consentJustGranted` flag in `process.ts`. Bootstrap welcome now only fires when consent transitions non-granted→granted in the current turn. Commit `8a58478`.
- **Fix 2 (benchmark provider)**: Changed bootstrap timezone step from "OK" → "Eastern". "Eastern" matches `TZ_KEYWORD_MAP` for `America/New_York`, avoids consent pattern. `givecare_provider.py` line 120.

### Baseline Benchmark Run (started 01:42 UTC, PID 2949409)
- Full 44-scenario run with fixed bootstrap
- Results will establish true dev-deployment baseline
- Expected completion: ~03:00-03:30 UTC

---
