import time

class FPSCounter:

    def __init__(self):

        self._start   = time.time()
        self._count   = 0
        self._fps     = 0.0

        # Rolling window for smoother FPS reading
        self._last_tick = time.time()

    def tick(self):

        self._count += 1

        now = time.time()
        elapsed = now - self._start

        if elapsed >= 1.0:
            self._fps   = self._count / elapsed
            self._count = 0
            self._start = now

    def get(self):

        return round(self._fps, 1)