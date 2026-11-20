// Wiring: connects the controls, the player state machine, and the renderer.
// All search logic lives on the server, transport in rpc.js, playback in
// player.js, and drawing in board.js.

import { QueensApi, RpcClient, STREAM_NOT_FOUND } from "./rpc.js";
import { SearchPlayer, State } from "./player.js";
import { BoardView } from "./board.js";
import { describe } from "./events.js";

const $ = (id) => document.getElementById(id);
const ui = {
  board: $("board"), size: $("size"), speed: $("speed"), speedOut: $("speed-out"),
  start: $("btn-start"), step: $("btn-step"), play: $("btn-play"), next: $("btn-next"), reset: $("btn-reset"),
  status: $("status"), state: $("state"), log: $("log"), solutions: $("solutions"),
  banner: $("banner"), bannerText: $("banner-text"), retry: $("btn-retry"), restart: $("btn-restart"),
  stats: Object.fromEntries([...document.querySelectorAll("[data-stat]")].map((el) => [el.dataset.stat, el])),
};

const LOG_LIMIT = 250;
const STATE_LABEL = {
  idle: "Not started", opening: "Opening stream", ready: "Paused", playing: "Playing",
  seeking: "Seeking next solution", finished: "Search complete", error: "Error",
};

// Slider 0..100 maps to 1000 ms .. 10 ms per event (log scale).
const speedToDelay = (v) => Math.round(1000 * Math.pow(0.01, v / 100));
const boardSize = () => Number(ui.size.value);

const api = new QueensApi(new RpcClient());
const view = new BoardView(ui.board);
let seekSkipped = 0;

const player = new SearchPlayer({
  api,
  delayMs: speedToDelay(Number(ui.speed.value)),
  listener: { onEvent, onState, onStats, onError },
});

// ---- listener callbacks ----------------------------------------------------

function onEvent(event, { fast }) {
  view.render(event);
  setStatus(describe(event, player.size), event.event);
  if (event.event === "solution") addSolution(event.board, player.stats.solution);
  if (fast && event.event !== "solution" && event.event !== "done") {
    seekSkipped++;
    return;
  }
  if (seekSkipped) {
    log("info", `Fast-forwarded through ${seekSkipped} events`);
    seekSkipped = 0;
  }
  log(event.event, describe(event, player.size));
}

function onState(state) {
  const idle = state === State.IDLE;
  const running = state === State.PLAYING || state === State.SEEKING;
  ui.start.textContent = idle ? "Start" : "Restart";
  ui.start.disabled = state === State.OPENING;
  ui.step.disabled = !(idle || state === State.READY);
  ui.play.textContent = running ? "Pause" : "Play";
  ui.play.setAttribute("aria-pressed", String(running));
  ui.play.disabled = !(idle || running || state === State.READY);
  ui.next.disabled = !(idle || state === State.READY || state === State.PLAYING);
  ui.reset.disabled = idle;
  ui.state.textContent = STATE_LABEL[state] ?? state;
  ui.state.dataset.state = state;

  if (state === State.FINISHED) {
    const n = player.stats.solution;
    showBanner("done", `Search complete: ${n} solution${n === 1 ? "" : "s"} found on ${player.size}×${player.size}. No further solutions remain.`, false);
  } else if (state !== State.ERROR) {
    hideBanner();
  }
}

function onStats(stats, p) {
  for (const key of ["solution", "events", "try", "place", "reject", "backtrack", "rpcCalls", "fetched"]) {
    if (ui.stats[key]) ui.stats[key].textContent = stats[key];
  }
  if (ui.stats.buffered) ui.stats.buffered.textContent = p.buffered;
}

function onError(error, { recoverable }) {
  let text;
  if (error.kind === "network") text = `${error.message}. Is the server still running?`;
  else if (error.code === STREAM_NOT_FOUND) text = "The server no longer knows this search stream (closed or expired). Restart to begin a new search.";
  else if (error.kind === "rpc") text = `Server error ${error.code}: ${error.message}`;
  else text = error.message;
  showBanner("error", text, recoverable);
  log("error", text);
}

// ---- view helpers ------------------------------------------------------------

function setStatus(text, kind = "info") {
  ui.status.textContent = text;
  ui.status.dataset.kind = kind;
}

function log(kind, text) {
  const li = document.createElement("li");
  li.dataset.kind = kind;
  const tag = document.createElement("span");
  tag.className = "tag";
  tag.textContent = kind;
  li.append(tag, document.createTextNode(text));
  ui.log.prepend(li);
  while (ui.log.childElementCount > LOG_LIMIT) ui.log.lastElementChild.remove();
}

function addSolution(board, n) {
  const li = document.createElement("li");
  li.textContent = `#${n}  [${board.join(", ")}]`;
  ui.solutions.append(li);
  li.scrollIntoView({ block: "nearest" });
}

function showBanner(kind, text, canRetry) {
  ui.banner.hidden = false;
  ui.banner.dataset.kind = kind;
  ui.bannerText.textContent = text;
  ui.retry.hidden = !(kind === "error" && canRetry);
}

function hideBanner() {
  ui.banner.hidden = true;
}

function clearView() {
  view.setSize(boardSize());
  ui.log.replaceChildren();
  ui.solutions.replaceChildren();
  seekSkipped = 0;
  setStatus("Press Start, Step, or Play to begin.");
}

// ---- actions -------------------------------------------------------------------

async function ensureStarted() {
  if (player.state !== State.IDLE) return true;
  return startSearch();
}

async function startSearch() {
  clearView();
  setStatus(`Opening a ${boardSize()}×${boardSize()} search…`);
  const ok = await player.start(boardSize());
  if (ok) {
    setStatus(`Stream open for ${boardSize()}×${boardSize()}. No search has run yet.`);
    log("info", `Opened ${boardSize()}×${boardSize()} stream`);
  }
  return ok;
}

const actions = {
  start: () => startSearch(),
  async step() {
    if (await ensureStarted()) await player.step();
  },
  async play() {
    if (player.state === State.PLAYING || player.state === State.SEEKING) return player.pause();
    if (await ensureStarted()) player.play();
  },
  async next() {
    if (await ensureStarted()) await player.nextSolution();
  },
  reset() {
    player.reset();
    clearView();
  },
};

ui.start.addEventListener("click", actions.start);
ui.step.addEventListener("click", actions.step);
ui.play.addEventListener("click", actions.play);
ui.next.addEventListener("click", actions.next);
ui.reset.addEventListener("click", actions.reset);
ui.restart.addEventListener("click", actions.start);
ui.retry.addEventListener("click", () => player.retry());

ui.size.addEventListener("change", actions.reset);
ui.speed.addEventListener("input", () => {
  const ms = speedToDelay(Number(ui.speed.value));
  ui.speedOut.textContent = `${ms} ms/event`;
  player.setDelay(ms);
});

document.addEventListener("keydown", (e) => {
  if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) return;
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  const key = { " ": "play", ArrowRight: "step", n: "next", N: "next", r: "reset", R: "reset", s: "start", S: "start" }[e.key];
  const button = key && ui[key];
  if (!button || button.disabled) return;
  e.preventDefault();
  actions[key]();
});

// Release the server-side stream when the page goes away (the TTL is the backstop).
addEventListener("pagehide", () => {
  if (player.streamId) api.closeOnUnload(player.streamId);
});

ui.speedOut.textContent = `${speedToDelay(Number(ui.speed.value))} ms/event`;
clearView();
onState(player.state);
onStats(player.stats, player);
