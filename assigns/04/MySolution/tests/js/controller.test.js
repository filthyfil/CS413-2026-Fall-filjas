// Controller tests with a substituted test backend. No view code is touched:
// the Controller is driven directly, exactly as the View would drive it.
import test from "node:test";
import assert from "node:assert/strict";

import { makeResult } from "../../web/js/backend.js";
import { AppController } from "../../web/js/controller.js";
import { AppModel, MAX_SOURCE_BYTES } from "../../web/js/model.js";

const PROGRAM = 'D0Eop2("+", D0Eint(20), D0Eint(22))';

function deferred() {
  let resolve;
  const promise = new Promise((r) => { resolve = r; });
  return { promise, resolve };
}

// Records calls; answers immediately unless told to hold or fail.
class FakeBackend {
  constructor() {
    this.calls = [];
    this.hold = new Map();      // op -> deferred
    this.throwOn = new Set();
  }
  #answer(op, req) {
    this.calls.push([op, req]);
    if (this.throwOn.has(op)) throw new Error(`${op} exploded`);
    if (this.hold.has(op)) return this.hold.get(op).promise;
    const status = op === "typecheck" || op === "compile" ? "not_implemented" : "ok";
    return Promise.resolve(makeResult(op, req.revision, status, `fake ${op}`));
  }
  lint(req) { return this.#answer("lint", req); }
  interpret(req) { return this.#answer("interpret", req); }
  typecheck(req) { return this.#answer("typecheck", req); }
  compile(req) { return this.#answer("compile", req); }
  execute(req) { return this.#answer("execute", req); }
  async cancel(req) {
    this.calls.push(["cancel", req]);
    const pending = this.hold.get("interpret");
    pending?.resolve(makeResult("interpret", this.lastRevision(), "cancelled", "stopped"));
  }
  lastRevision() { return this.calls.findLast(([op]) => op === "interpret")[1].revision; }
}

function setup() {
  const model = new AppModel();
  const backend = new FakeBackend();
  let n = 0;
  const controller = new AppController(model, backend, {
    examples: { factorial: { name: "Factorial (canned)", text: PROGRAM } },
    newRunId: () => `run-${(n += 1)}`,
  });
  return { model, backend, controller };
}

const file = (name, bytes) => ({
  name,
  size: bytes.length,
  arrayBuffer: async () => bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.length),
});

test("each button dispatches to the matching backend operation", async () => {
  const { model, backend, controller } = setup();
  controller.loadExample("factorial");
  for (const op of ["lint", "interpret", "typecheck", "compile"]) {
    await controller.run(op);
  }
  assert.deepEqual(backend.calls.map(([op]) => op),
    ["lint", "interpret", "typecheck", "compile"]);
  assert.deepEqual(backend.calls[1][1], { source: PROGRAM, revision: 1, runId: "run-2" });
  assert.deepEqual(model.results.map((r) => r.op),
    ["compile", "typecheck", "interpret", "lint"]);
});

test("placeholders are not successes and execute stays unavailable", async () => {
  const { model, backend, controller } = setup();
  controller.loadExample("factorial");
  await controller.run("typecheck");
  await controller.run("compile");
  assert.ok(model.results.every((r) => r.status === "not_implemented"));
  const r = await controller.run("execute");
  assert.equal(r.ok, false);
  assert.ok(!backend.calls.some(([op]) => op === "execute"));
});

test("nothing is dispatched without applied source or with unapplied edits", async () => {
  const { model, backend, controller } = setup();
  assert.equal((await controller.run("lint")).ok, false);
  controller.manualInput();
  controller.edit(PROGRAM);
  assert.equal((await controller.run("lint")).ok, false);
  controller.apply();
  assert.ok((await controller.run("lint")).ok);
  assert.equal(backend.calls.length, 1);
  assert.equal(model.applied.name, "Manual input");
});

test("busy while the backend works; controls restored afterwards", async () => {
  const { model, backend, controller } = setup();
  controller.loadExample("factorial");
  const pending = deferred();
  backend.hold.set("lint", pending);
  const running = controller.run("lint");
  assert.equal(model.busy.op, "lint");
  assert.equal(model.canRun("interpret"), false);
  assert.equal((await controller.run("interpret")).ok, false);  // conflicting action
  assert.equal(controller.edit("D0Eint(1)").ok, false);          // conflicting edit
  pending.resolve(makeResult("lint", 1, "ok", "fine"));
  await running;
  assert.equal(model.busy, null);
  assert.ok(model.canRun("interpret"));
});

test("a throwing backend becomes a failure result; retry succeeds", async () => {
  const { model, backend, controller } = setup();
  controller.loadExample("factorial");
  backend.throwOn.add("interpret");
  await controller.run("interpret");
  const [failed] = model.results;
  assert.equal(failed.status, "failure");
  assert.equal(failed.errorKind, "backend");
  assert.match(failed.message, /exploded/);
  assert.equal(model.busy, null);
  assert.equal(model.applied.text, PROGRAM);
  assert.equal(model.retryOp, "interpret");

  backend.throwOn.clear();
  await controller.retry();
  assert.equal(model.results[0].status, "ok");
  assert.equal(model.retryOp, null);
});

test("a failure result from the backend (e.g. server down) is shown", async () => {
  const { model, backend, controller } = setup();
  controller.loadExample("factorial");
  backend.hold.set("lint", { promise: Promise.resolve(
    makeResult("lint", 1, "failure", "Could not reach the server", { errorKind: "backend" })) });
  await controller.run("lint");
  assert.equal(model.results[0].status, "failure");
  assert.equal(model.retryOp, "lint");
});

test("stop cancels a running interpret by its run id", async () => {
  const { model, backend, controller } = setup();
  controller.loadExample("factorial");
  backend.hold.set("interpret", deferred());
  const running = controller.run("interpret");
  assert.equal(model.busy.op, "interpret");
  await controller.stop();
  await running;
  assert.deepEqual(backend.calls.at(-1), ["cancel", { runId: "run-1" }]);
  assert.equal(model.busy, null);
  assert.equal(model.results[0].status, "cancelled");
  assert.equal(model.retryOp, "interpret");
});

test("stop does nothing when idle", async () => {
  const { backend, controller } = setup();
  await controller.stop();
  assert.deepEqual(backend.calls, []);
});

test("upload: valid UTF-8 file becomes a new revision", async () => {
  const { model, controller } = setup();
  const r = await controller.uploadFile(file("p.txt", new TextEncoder().encode(PROGRAM)));
  assert.ok(r.ok);
  assert.deepEqual(model.applied, { name: "p.txt", text: PROGRAM, revision: 1 });
});

test("upload: invalid UTF-8 and oversized files are rejected, applied source kept", async () => {
  const { model, controller } = setup();
  controller.loadExample("factorial");
  const bad = await controller.uploadFile(file("bad.txt", new Uint8Array([0x44, 0xff, 0xfe])));
  assert.equal(bad.ok, false);
  assert.match(model.notice.text, /UTF-8/);
  const big = { name: "big.txt", size: MAX_SOURCE_BYTES + 1,
    arrayBuffer: async () => { throw new Error("must not be read"); } };
  assert.equal((await controller.uploadFile(big)).ok, false);
  assert.match(model.notice.text, /limit/);
  const empty = await controller.uploadFile(file("e.txt", new TextEncoder().encode("  \n")));
  assert.equal(empty.ok, false);
  assert.deepEqual(model.applied, { name: "Factorial (canned)", text: PROGRAM, revision: 1 });
});

test("upload is refused while edits are unapplied", async () => {
  const { model, controller } = setup();
  controller.loadExample("factorial");
  controller.edit("D0Eint(1)");
  const r = await controller.uploadFile(file("p.txt", new TextEncoder().encode("D0Eint(2)")));
  assert.equal(r.ok, false);
  assert.equal(model.draft.text, "D0Eint(1)");
  assert.equal(model.applied.revision, 1);
});
