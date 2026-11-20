// Required test 10 (automated part): the logic behind Start/Reset, Step,
// Play/Pause, Next solution, and RPC failure handling, driven through the
// real SearchPlayer with a fake API and a manual clock.

import { test } from "node:test";
import assert from "node:assert/strict";

import { BATCH, SearchPlayer, State } from "../../client/player.js";
import { RpcError } from "../../client/rpc.js";
import { FakeApi, ManualScheduler, deferred, referenceTrace, settle } from "./fakes.mjs";

function setup() {
  const api = new FakeApi();
  const clock = new ManualScheduler();
  const seen = { events: [], states: [], errors: [] };
  const player = new SearchPlayer({
    api, delayMs: 50, schedule: clock.schedule, cancel: clock.cancel,
    listener: {
      onEvent: (e, info) => seen.events.push({ ...e, fast: info.fast }),
      onState: (s) => seen.states.push(s),
      onError: (e, info) => seen.errors.push({ e, recoverable: info.recoverable }),
    },
  });
  return { api, clock, seen, player };
}

test("start opens a stream and fetches nothing", async () => {
  const { api, player } = setup();
  assert.equal(player.state, State.IDLE);
  assert.equal(await player.start(8), true);
  assert.equal(player.state, State.READY);
  assert.deepEqual(api.calls, [["open", 8]]);
});

test("step shows exactly one event per click and fetches in small batches", async () => {
  const { api, seen, player } = setup();
  await player.start(8);
  const trace = referenceTrace(8);
  for (let i = 0; i < 6; i++) await player.step();
  assert.deepEqual(seen.events.map(({ fast, ...e }) => e), trace.slice(0, 6));
  assert.deepEqual(api.calls.slice(1), [["next", "s1", BATCH.step], ["next", "s1", BATCH.step]]);
  assert.equal(player.stats.fetched, 8);
  assert.equal(player.buffered, 2);
});

test("play advances one event per timer tick and pause stops it", async () => {
  const { clock, seen, player } = setup();
  await player.start(6);
  player.play();
  await settle();
  assert.equal(player.state, State.PLAYING);
  assert.equal(seen.events.length, 1);
  await clock.fire();
  await clock.fire();
  assert.equal(seen.events.length, 3);
  player.pause();
  assert.equal(player.state, State.READY);
  assert.equal(clock.pending, 0);
  await clock.fire();
  assert.equal(seen.events.length, 3);
});

test("next solution runs to the first solution, then the next one", async () => {
  const { api, seen, player } = setup();
  await player.start(8);
  const first = await player.nextSolution();
  assert.deepEqual(first, { event: "solution", board: [0, 4, 7, 5, 2, 6, 1, 3] });
  assert.equal(player.state, State.READY);
  const firstSolution = referenceTrace(8).findIndex((e) => e.event === "solution") + 1;
  assert.equal(firstSolution, 1858);
  assert.equal(seen.events.length, firstSolution);
  assert.ok(seen.events.slice(0, -1).every((e) => e.fast));
  assert.ok(api.calls.filter((c) => c[0] === "next").every((c) => c[2] <= 32));
  const second = await player.nextSolution();
  assert.deepEqual(second.board, [0, 5, 7, 2, 6, 3, 1, 4]);
});

test("whole 8x8 flow: 92 solutions, done once, stream closed, then restartable", async () => {
  const { api, seen, player } = setup();
  await player.start(8);
  while (player.state === State.READY) await player.nextSolution();
  assert.equal(player.state, State.FINISHED);
  assert.equal(player.stats.solution, 92);
  assert.equal(new Set(player.stats.solutions.map(String)).size, 92);
  assert.equal(seen.events.filter((e) => e.event === "done").length, 1);
  assert.equal(seen.events.at(-1).event, "done");
  assert.equal(player.stats.fetched, referenceTrace(8).length);   // nothing fetched beyond done
  assert.deepEqual(api.calls.at(-1), ["close", "s1"]);
  assert.equal(await player.step(), null);                         // nothing after completion
  await player.start(8);                                           // restart after completion
  assert.equal(player.state, State.READY);
  assert.equal(player.stats.events, 0);
});

test("reset closes the stream and ignores a response still in flight", async () => {
  const { api, seen, player } = setup();
  await player.start(8);
  const gate = deferred();
  api.hold = gate.promise;
  const pending = player.step();
  player.reset();
  assert.equal(player.state, State.IDLE);
  assert.deepEqual(api.calls.at(-1), ["close", "s1"]);
  api.hold = null;
  gate.resolve();
  await pending;
  assert.equal(seen.events.length, 0);          // stale events never reach the UI
  assert.equal(player.state, State.IDLE);
});

test("controls are ignored in states where they do not apply", async () => {
  const { api, player } = setup();
  assert.equal(await player.step(), null);       // idle: main.js auto-starts instead
  player.play();
  assert.equal(player.state, State.IDLE);
  assert.equal(api.calls.length, 0);
});

test("network failure shows an error, and retry continues on the same stream", async () => {
  const { api, seen, player } = setup();
  await player.start(5);
  await player.step();
  player.buffer.length = 0;
  api.failNext = new RpcError("Network error: cannot reach the server", { kind: "network" });
  await player.step();
  assert.equal(player.state, State.ERROR);
  assert.equal(seen.errors.length, 1);
  assert.equal(seen.errors[0].recoverable, true);
  assert.equal(await player.retry(), true);
  assert.equal(player.state, State.READY);
  await player.step();
  assert.equal(seen.events.length, 2);
});

test("failure during playback stops the timer", async () => {
  const { api, clock, player } = setup();
  await player.start(5);
  player.play();
  await settle();
  player.buffer.length = 0;
  api.failNext = new RpcError("Server returned HTTP 502", { kind: "http", status: 502 });
  await clock.fire();
  assert.equal(player.state, State.ERROR);
  assert.equal(clock.pending, 0);
});

test("an expired stream is not resumable; retry opens a new stream", async () => {
  const { api, seen, player } = setup();
  await player.start(5);
  api.streams.clear();                          // the server forgot the stream
  await player.step();
  assert.equal(player.state, State.ERROR);
  assert.equal(seen.errors[0].recoverable, false);
  await player.retry();
  assert.equal(player.state, State.READY);
  assert.equal(player.streamId, "s2");
  assert.equal(api.count("open"), 2);
});

test("opening failure is reported and retry reopens", async () => {
  const { api, player } = setup();
  const realOpen = api.open.bind(api);
  api.open = async () => { throw new RpcError("Network error: cannot reach the server", { kind: "network" }); };
  await player.start(8);
  assert.equal(player.state, State.ERROR);
  assert.equal(player.canResume(), false);
  api.open = realOpen;
  await player.retry();
  assert.equal(player.state, State.READY);
});
