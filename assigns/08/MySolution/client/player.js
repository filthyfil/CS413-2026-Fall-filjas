// Playback state machine: owns the stream ID and a small event buffer, and
// asks the server for the next batch only when the buffer runs dry. It never
// fetches the whole trace: each queens.next asks for at most 32 events, and
// only while the user is stepping, playing, or seeking.
//
// No DOM here. The API and timer functions are injected, so Node tests can
// drive it with a fake server and a fake clock.
//
// States
//   idle      no stream
//   opening   queens.open in flight
//   ready     stream open, paused (Step / Play / Next solution allowed)
//   playing   timed playback, one event per `delayMs`
//   seeking   "Next solution": consume events quickly until solution/done
//   finished  `done` was shown; the stream is closed
//   error     last RPC failed; see `lastError` and retry()

import { STREAM_NOT_FOUND } from "./rpc.js";

export const State = Object.freeze({
  IDLE: "idle", OPENING: "opening", READY: "ready", PLAYING: "playing",
  SEEKING: "seeking", FINISHED: "finished", ERROR: "error",
});

// Events per queens.next call for each activity. Small for manual stepping,
// larger for fast consumption. All are well under the server's 32 cap.
export const BATCH = Object.freeze({ step: 4, play: 16, seek: 32 });

const STALE = Symbol("stale");

function freshStats() {
  return { events: 0, try: 0, place: 0, reject: 0, backtrack: 0, solution: 0,
           rpcCalls: 0, fetched: 0, solutions: [] };
}

export class SearchPlayer {
  constructor({ api, delayMs = 100, schedule = (fn, ms) => setTimeout(fn, ms),
                cancel = (id) => clearTimeout(id), listener = {} }) {
    this.api = api;
    this.delayMs = delayMs;
    this.schedule = schedule;
    this.cancel = cancel;
    this.listener = listener;
    this.state = State.IDLE;
    this.generation = 0;       // bumped by reset/start; stale async work checks it
    this.size = null;
    this.lastError = null;
    this._clear();
  }

  _clear() {
    this.streamId = null;
    this.buffer = [];
    this.serverDone = false;
    this.lastEvent = null;
    this.stats = freshStats();
    this._timer = null;
    this._inflight = null;     // promise of the step/tick/seek currently running
  }

  get buffered() {
    return this.buffer.length;
  }

  _setState(state) {
    if (this.state === state) return;
    this.state = state;
    this.listener.onState?.(state, this);
  }

  _emitStats() {
    this.listener.onStats?.(this.stats, this);
  }

  // ---- lifecycle ------------------------------------------------------------

  reset() {
    this.generation++;
    if (this._timer !== null) this.cancel(this._timer);
    if (this.streamId !== null) this.api.close(this.streamId).catch(() => {});
    this._clear();
    this.lastError = null;
    this._setState(State.IDLE);
    this._emitStats();
  }

  async start(size) {
    this.reset();
    const gen = this.generation;
    this.size = size;
    this._setState(State.OPENING);
    try {
      this.stats.rpcCalls++;
      const result = await this.api.open(size);
      if (gen !== this.generation) {           // reset while opening
        this.api.close(result.stream_id).catch(() => {});
        return false;
      }
      this.streamId = result.stream_id;
      this._setState(State.READY);
      this._emitStats();
      return true;
    } catch (error) {
      if (gen === this.generation) this._fail(error);
      return false;
    }
  }

  // ---- consuming events -----------------------------------------------------

  // Next event: from the buffer, or one queens.next call when it is empty.
  // Returns null once the stream is finished, or STALE if a reset happened
  // while the request was in flight.
  async _pull(limit) {
    if (this.buffer.length === 0 && !this.serverDone) {
      const gen = this.generation;
      this.stats.rpcCalls++;
      const result = await this.api.next(this.streamId, limit);
      if (gen !== this.generation) return STALE;
      this.buffer.push(...result.events);
      this.stats.fetched += result.events.length;
      this.serverDone = result.done;
    }
    return this.buffer.length ? this.buffer.shift() : null;
  }

  _deliver(event, fast = false) {
    const s = this.stats;
    s.events++;
    if (event.event in s) s[event.event]++;
    if (event.event === "solution") s.solutions.push(event.board);
    this.lastEvent = event;
    this.listener.onEvent?.(event, { fast, player: this });
    this._emitStats();
    if (event.event === "done") this._finish();
  }

  _finish() {
    if (this._timer !== null) this.cancel(this._timer);
    this._timer = null;
    // The server already released solver state; close drops the ID too.
    if (this.streamId !== null) this.api.close(this.streamId).catch(() => {});
    this.streamId = null;
    this._setState(State.FINISHED);
  }

  _fail(error) {
    if (this._timer !== null) this.cancel(this._timer);
    this._timer = null;
    this.lastError = error;
    this._setState(State.ERROR);
    this.listener.onError?.(error, { recoverable: this.canResume(), player: this });
  }

  // Run one unit of consuming work; at most one runs at a time.
  async _exclusive(work) {
    if (this._inflight) return null;
    const gen = this.generation;
    const run = (async () => {
      try {
        return await work(gen);
      } catch (error) {
        if (gen === this.generation) this._fail(error);
        return null;
      }
    })();
    this._inflight = run;
    try {
      return await run;
    } finally {
      if (gen === this.generation) this._inflight = null;
    }
  }

  async _consumeOne(gen, limit, fast = false) {
    const event = await this._pull(limit);
    if (event === STALE || gen !== this.generation) return STALE;
    if (event === null) {
      this._finish();
      return null;
    }
    this._deliver(event, fast);
    return event;
  }

  step() {
    if (this.state !== State.READY) return Promise.resolve(null);
    return this._exclusive(async (gen) => {
      const event = await this._consumeOne(gen, BATCH.step);
      return event === STALE ? null : event;
    });
  }

  play() {
    if (this.state !== State.READY || this._inflight) return;
    this._setState(State.PLAYING);
    this._tick();
  }

  async _tick() {
    this._timer = null;
    if (this.state !== State.PLAYING) return;
    const gen = this.generation;
    await this._exclusive((g) => this._consumeOne(g, BATCH.play));
    if (gen === this.generation && this.state === State.PLAYING) {
      this._timer = this.schedule(() => this._tick(), this.delayMs);
    }
  }

  // Stop timed playback or seeking. An in-flight request still delivers its
  // event, so nothing fetched is ever skipped.
  pause() {
    if (this.state !== State.PLAYING && this.state !== State.SEEKING) return;
    if (this._timer !== null) this.cancel(this._timer);
    this._timer = null;
    this._setState(State.READY);
  }

  // Consume events until the next solution (or done). Pauses playback first.
  async nextSolution() {
    if (this.state === State.PLAYING) {
      this.pause();
      await this._inflight;
    }
    if (this.state !== State.READY || this._inflight) return null;
    this._setState(State.SEEKING);
    return this._exclusive(async (gen) => {
      while (gen === this.generation && this.state === State.SEEKING) {
        const event = await this._consumeOne(gen, BATCH.seek, true);
        if (event === STALE) return null;
        if (event === null || event.event === "solution" || event.event === "done") {
          if (this.state === State.SEEKING) this._setState(State.READY);
          return event;
        }
      }
      return null;   // paused or reset mid-seek
    });
  }

  setDelay(ms) {
    this.delayMs = ms;
    if (this.state === State.PLAYING && this._timer !== null) {
      this.cancel(this._timer);
      this._timer = this.schedule(() => this._tick(), this.delayMs);
    }
  }

  // ---- errors -----------------------------------------------------------------

  // True when the failed request can be retried on the same stream: queens.next
  // is all-or-nothing on the server, so retrying loses no events. False when
  // there is no stream yet or the server no longer knows it.
  canResume() {
    return this.streamId !== null && this.lastError?.code !== STREAM_NOT_FOUND;
  }

  // Back to `ready` on the same stream if possible; otherwise reopen.
  async retry() {
    if (this.state !== State.ERROR) return false;
    if (this.canResume()) {
      this.lastError = null;
      this._setState(State.READY);
      return true;
    }
    return this.start(this.size);
  }
}
