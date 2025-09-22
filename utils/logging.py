import logging
import time


class StageTimer:
    def __init__(self, name: str):
        self.name = name
        self.t0 = time.time()

    def done(self, ok: bool = True):
        dt = time.time() - self.t0
        level = logging.INFO if ok else logging.ERROR
        logging.log(level, "%s finished in %.2fs", self.name, dt)

