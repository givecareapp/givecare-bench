/** In-memory browser-only pagination guard; it never persists cursors or rows. */

export type LedgerChronologyRow = { entry_id: string; appended_at: string };

function timestampNanoseconds(value: string): bigint | null {
  const match = /^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,9}))?Z$/.exec(value);
  if (!match) return null;
  const milliseconds = Date.parse(`${match[1]}Z`);
  if (Number.isNaN(milliseconds) || new Date(milliseconds).toISOString().slice(0, 19) !== match[1]) {
    return null;
  }
  return BigInt(milliseconds) * 1_000_000n + BigInt((match[2] ?? "").padEnd(9, "0") || "0");
}

export class LedgerPagination {
  #generation = 0;
  #inFlight = false;
  #seen = new Set<string>();
  #latest: bigint | null = null;

  begin(): number | null {
    if (this.#inFlight) return null;
    this.#inFlight = true;
    this.#generation += 1;
    return this.#generation;
  }

  isCurrent(generation: number): boolean {
    return this.#inFlight && generation === this.#generation;
  }

  accept(generation: number, continuation: boolean, rows: LedgerChronologyRow[]): boolean {
    if (!this.isCurrent(generation)) return false;
    const nextSeen = continuation ? new Set(this.#seen) : new Set<string>();
    let previous = continuation ? this.#latest : null;
    for (const row of rows) {
      const current = timestampNanoseconds(row.appended_at);
      if (current === null || nextSeen.has(row.entry_id) || (previous !== null && current < previous)) {
        return false;
      }
      nextSeen.add(row.entry_id);
      previous = current;
    }
    this.#seen = nextSeen;
    this.#latest = previous;
    return true;
  }

  finish(generation: number): void {
    if (generation === this.#generation) this.#inFlight = false;
  }
}
