"""Runs Interpret in a child process so the user can stop it.

Python threads cannot be killed from outside, so each run gets its own
process (``spawn`` start method). The HTTP request thread waits for the
child's answer; ``cancel(run_id)`` from another request kills the child.
Starting a new run also stops any run left over from before (one user).
There is deliberately no time limit: the user decides when to stop.
"""
import multiprocessing
import sys
import threading
from dataclasses import dataclass

# Interpreted programs recurse once per LAMBDA call, so the child raises
# Python's recursion limit and runs the evaluator on a thread with a big stack.
CHILD_RECURSION_LIMIT = 100_000
CHILD_STACK_BYTES = 512 * 1024 * 1024


@dataclass
class RunOutcome:
    result: tuple | None = None     # evaluate_source(...) return value
    cancelled: bool = False
    crash: str | None = None        # child died without answering


def _child_main(conn, source: str) -> None:
    from .tools import evaluate_source  # imported here: tools imports runner

    box = {}

    def work():
        try:
            box["result"] = evaluate_source(source)
        except RecursionError:
            box["result"] = ("error", "Runtime error: recursion too deep "
                             "(RecursionError)", "runtime", None)

    sys.setrecursionlimit(CHILD_RECURSION_LIMIT)
    sys.set_int_max_str_digits(0)  # print big results such as fact(5000)
    try:
        threading.stack_size(CHILD_STACK_BYTES)
    except (ValueError, RuntimeError):
        pass
    worker = threading.Thread(target=work)
    worker.start()
    worker.join()
    conn.send(box.get("result", ("error", "Runtime error: evaluation "
                                 "aborted", "runtime", None)))
    conn.close()


@dataclass
class _Job:
    process: multiprocessing.Process
    cancelled: bool = False


class InterpretRunner:
    def __init__(self, poll_seconds: float = 0.05):
        self._ctx = multiprocessing.get_context("spawn")
        self._poll = poll_seconds
        self._lock = threading.Lock()
        self._jobs: dict[str, _Job] = {}
        self._early_cancels: set[str] = set()

    def run(self, source: str, run_id: str) -> RunOutcome:
        recv_conn, send_conn = self._ctx.Pipe(duplex=False)
        proc = self._ctx.Process(target=_child_main, args=(send_conn, source),
                                 daemon=True)
        job = _Job(proc)
        with self._lock:
            if run_id in self._jobs:
                raise ValueError(f"run id {run_id!r} is already running")
            # Single user, one run at a time: anything still running was
            # abandoned (e.g. the tab was closed), so stop it.
            orphans = list(self._jobs.values())
            for orphan in orphans:
                orphan.cancelled = True
            self._jobs[run_id] = job
            if run_id in self._early_cancels:
                self._early_cancels.discard(run_id)
                job.cancelled = True
        for orphan in orphans:
            self._kill(orphan.process)
        try:
            if job.cancelled:
                return RunOutcome(cancelled=True)
            proc.start()
            send_conn.close()
            while True:
                if job.cancelled:
                    return RunOutcome(cancelled=True)
                if recv_conn.poll(self._poll):
                    try:
                        return RunOutcome(result=recv_conn.recv())
                    except EOFError:
                        pass  # child exited without sending
                    proc.join(1)
                    if job.cancelled:
                        return RunOutcome(cancelled=True)
                    return RunOutcome(crash=f"exit code {proc.exitcode}")
        finally:
            with self._lock:
                self._jobs.pop(run_id, None)
            self._kill(proc)
            recv_conn.close()

    def cancel(self, run_id: str) -> bool:
        """Stop a run. Returns False if no such run is in progress."""
        with self._lock:
            job = self._jobs.get(run_id)
            if job is None:
                # The cancel may overtake its interpret request; remember it.
                self._early_cancels.add(run_id)
                if len(self._early_cancels) > 100:
                    self._early_cancels.pop()
                return False
            job.cancelled = True
        self._kill(job.process)
        return True

    def active_runs(self) -> list[str]:
        with self._lock:
            return list(self._jobs)

    def shutdown(self) -> None:
        with self._lock:
            jobs = list(self._jobs.values())
            for job in jobs:
                job.cancelled = True
        for job in jobs:
            self._kill(job.process)

    @staticmethod
    def _kill(proc: multiprocessing.Process) -> None:
        if proc.pid is not None and proc.is_alive():
            proc.kill()
        if proc.pid is not None:
            proc.join(5)
