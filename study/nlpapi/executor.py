import threading
import time
from collections.abc import Callable

from scattermind.system.base import ExecutorId, L_EITHER, Locality
from scattermind.system.executor.executor import Executor, ExecutorManager
from scattermind.system.logger.context import add_context
from scattermind.system.logger.log import EventStream


LOCK = threading.RLock()
EXECUTORS: dict[ExecutorId, 'ThreadExecutorManager'] = {}
ACTIVE: dict[ExecutorId, bool] = {}


class ThreadExecutorManager(ExecutorManager):
    def __init__(
            self,
            own_id: ExecutorId,
            *,
            batch_size: int,
            sleep_on_idle: float) -> None:
        super().__init__(own_id, batch_size)
        self._sleep_on_idle = sleep_on_idle
        self._thread: threading.Thread | None = None
        self._work: Callable[[ExecutorManager], bool] | None = None
        self._logger: EventStream | None = None
        self._done = False
        with LOCK:
            EXECUTORS[own_id] = self
            ACTIVE[own_id] = True

    def is_done(self) -> bool:
        return self._done

    def set_done(self, is_done: bool) -> None:
        self._done = is_done

    def _maybe_start(self) -> None:
        assert self._logger is not None
        logger = self._logger

        def run() -> None:
            with add_context({"executor": self.get_own_id()}):
                running = True
                logger.log_event(
                    "tally.executor.start",
                    {
                        "name": "executor",
                        "action": "start",
                    })
                try:
                    while not self.is_done() and thread is self._thread:
                        work = self._work
                        if work is None:
                            raise ValueError("uninitialized executor")
                        sleep_on_idle = self._sleep_on_idle
                        if not work(self) and sleep_on_idle > 0.0:
                            time.sleep(sleep_on_idle)
                    running = False
                finally:
                    with LOCK:
                        ACTIVE[self.get_own_id()] = False
                        self._thread = None
                        if running:
                            logger.log_error(
                                "error.executor", "uncaught_executor")
                    logger.log_event(
                        "tally.executor.stop",
                        {
                            "name": "executor",
                            "action": "stop",
                        })

        if self._thread is not None:
            return
        with LOCK:
            if self._thread is not None:
                return
            if self.is_done() or not self.is_active(self.get_own_id()):
                raise ValueError("attempt to start inactive executor")
            thread = threading.Thread(
                target=run,
                daemon=False)
            self._thread = thread
            thread.start()

    @staticmethod
    def locality() -> Locality:
        return L_EITHER

    def get_all_executors(self) -> list[Executor]:
        with LOCK:
            return [emng.as_executor() for emng in EXECUTORS.values()]

    def is_active(self, executor_id: ExecutorId) -> bool:
        with LOCK:
            return ACTIVE[executor_id]

    def release_executor(self, executor_id: ExecutorId) -> None:
        with LOCK:
            executor = EXECUTORS[executor_id]
            if executor is not None:
                executor.set_done(True)

    def get_work(self) -> Callable[[ExecutorManager], bool] | None:
        return self._work

    def get_logger(self) -> EventStream | None:
        return self._logger

    def execute(
            self,
            logger: EventStream,
            work: Callable[[ExecutorManager], bool]) -> None:
        if self._work is not work or self._logger is not logger:
            self._work = work
            self._logger = logger
            self._maybe_start()
            # NOTE: propagate the work to all other thread executors
            # this is only needed / possible for local executors
            with LOCK:
                executors = list(EXECUTORS.values())
            for exe in executors:
                is_active = exe.is_active(exe.get_own_id())
                same_work = exe.get_work() is work
                same_logger = self.get_logger() is logger
                if (not same_work or not same_logger) and is_active:
                    exe.execute(logger, work)
