import assert from "node:assert/strict";
import test from "node:test";

import { LedgerPagination } from "./intake-ledger-pagination.ts";

test("ledger pagination ignores delayed double-clicks and rejects duplicate or regressing continuation rows", () => {
  const pages = new LedgerPagination();
  const first = pages.begin();
  assert.equal(first, 1);
  assert.equal(pages.begin(), null, "the same cursor cannot be dispatched while the first call is pending");
  assert.equal(
    pages.accept(first, false, [{ entry_id: "a".repeat(64), appended_at: "2026-08-02T07:15:00Z" }]),
    true,
  );
  pages.finish(first);

  const replacement = pages.begin();
  assert.equal(replacement, 2);
  assert.equal(
    pages.accept(first, true, [{ entry_id: "c".repeat(64), appended_at: "2026-08-02T07:16:00Z" }]),
    false,
    "a response from an older generation is ignored after a retry begins",
  );
  pages.finish(replacement);

  const continuation = pages.begin();
  assert.equal(continuation, 3);
  assert.equal(
    pages.accept(continuation, true, [{ entry_id: "a".repeat(64), appended_at: "2026-08-02T07:16:00Z" }]),
    false,
    "a delayed duplicate continuation must not append a duplicate row",
  );
  pages.finish(continuation);

  const regressing = pages.begin();
  assert.equal(regressing, 4);
  assert.equal(
    pages.accept(regressing, true, [{ entry_id: "b".repeat(64), appended_at: "2026-08-02T07:14:59.999999999Z" }]),
    false,
    "continuations cannot regress chronologically",
  );
  pages.finish(regressing);
});
