import threading
import time


class RepeatingTimer(object):
    def __init__(self, interval, target, *args, **kwargs):
        self.interval = interval
        self.target = target
        self.args = args
        self.kwargs = kwargs
        self.is_running = False

        self._stop_event = threading.Event()

        self._start_time = 0

    def start(self):
        if self.is_running:
            return
        self._stop_event.clear()
        self.is_running = True

        next_time = time.time()

        while not self._stop_event.is_set():
            next_time += self.interval
            delta = next_time - time.time()
            if delta > 0:
                self._stop_event.wait(delta)
                if self._stop_event.is_set():
                    return
            self.target(*self.args, **self.kwargs)

    def start_async(self, *args, **kwargs):
        threading.Thread(*args, **kwargs, target=self.start).start()

    def stop(self):
        self._stop_event.set()
        self.is_running = False
