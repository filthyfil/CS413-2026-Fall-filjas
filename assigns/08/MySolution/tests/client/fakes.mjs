// Test doubles for the client tests: a reference trace generator (the same
// event model as tests/_support.py), an in-memory queens API that records
// every call, and a manual scheduler standing in for setTimeout.

import { RpcError, STREAM_NOT_FOUND } from "../../client/rpc.js";

export function referenceTrace(n) {
  const events = [];
  const safe = (board, row, col) => board.every((c, r) => c !== col && Math.abs(c - col) !== row - r);
  const search = (row, board) => {
    for (let column = 0; column < n; column++) {
      events.push({ event: "try", column, row, board });
      if (!safe(board, row, column)) {
        events.push({ event: "reject", column, row, board });
        continue;
      }
      const placed = [...board, column];
      events.push({ event: "place", column, row, board: placed });
      if (row + 1 === n) events.push({ event: "solution", board: placed });
      else search(row + 1, placed);
      events.push({ event: "backtrack", column, row, board });
    }
  };
  search(0, []);
  events.push({ event: "done" });
  return events;
}

export class FakeApi {
  constructor() {
    this.calls = [];
    this.streams = new Map();
    this.ids = 0;
    this.failNext = null;     // an Error to throw from the next `next` call
    this.hold = null;         // when set, `next` waits on this promise first
  }

  async open(size) {
    this.calls.push(["open", size]);
    const id = `s${++this.ids}`;
    this.streams.set(id, { trace: referenceTrace(size), pos: 0 });
    return { stream_id: id, size };
  }

  async next(id, limit) {
    this.calls.push(["next", id, limit]);
    if (this.hold) await this.hold;
    if (this.failNext) {
      const e = this.failNext;
      this.failNext = null;
      throw e;
    }
    const s = this.streams.get(id);
    if (!s) throw new RpcError("Unknown stream", { kind: "rpc", code: STREAM_NOT_FOUND });
    const events = s.trace.slice(s.pos, s.pos + limit);
    s.pos += events.length;
    return { events, done: s.pos >= s.trace.length };
  }

  async close(id) {
    this.calls.push(["close", id]);
    if (!this.streams.delete(id)) throw new RpcError("Unknown stream", { kind: "rpc", code: STREAM_NOT_FOUND });
    return { closed: true };
  }

  count(method) {
    return this.calls.filter((c) => c[0] === method).length;
  }
}

export class ManualScheduler {
  constructor() {
    this.timers = new Map();
    this.nextId = 0;
    this.schedule = (fn, ms) => {
      const id = ++this.nextId;
      this.timers.set(id, { fn, ms });
      return id;
    };
    this.cancel = (id) => this.timers.delete(id);
  }

  get pending() {
    return this.timers.size;
  }

  // Fire every pending timer once, then let the resulting async work settle.
  async fire() {
    const due = [...this.timers.values()];
    this.timers.clear();
    for (const t of due) t.fn();
    await settle();
  }
}

export const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

export function deferred() {
  let resolve;
  const promise = new Promise((r) => { resolve = r; });
  return { promise, resolve };
}
