import numpy as np


class StreamAggr(object):
    TMP_MEM_SIZE = 2 ** 20
    GC_SIZE = 2 ** 20 - 1
    TIME_OFFSET = 0.1

    def __init__(self, window_size, window_type='s'):
        self.times = np.zeros(StreamAggr.TMP_MEM_SIZE, dtype=int)
        self.values = np.zeros(StreamAggr.TMP_MEM_SIZE, dtype=float)
        self.prev_start = self.prev_end = 0
        self.curr_start = self.curr_end = 0
        if window_type not in ('s', 'ms'):
            raise ValueError("window_type must be 's' or 'ms'")
        self.window_size = window_size * (1000 if window_type == 's' else 1)
        self.window_type = window_type
        self._sum = 0
        self._sum2 = 0
        self._count = 0

    def feed(self, timestamp, value):
        self.times[self.curr_end] = int(timestamp)
        self.values[self.curr_end] = value
        self._sum += value
        self._sum2 += value ** 2
        self._count += 1
        idx = np.searchsorted(self.times[self.prev_start:self.curr_end],
                              timestamp + StreamAggr.TIME_OFFSET - self.window_size)
        self.curr_start = self.prev_start + idx
        window_slide = self.values[self.prev_start:self.curr_start]
        self._sum -= np.sum(window_slide)
        self._sum2 -= np.sum(window_slide ** 2)
        self._count -= idx
        self.prev_start = self.curr_start
        self.prev_end = self.curr_end
        self.curr_end += 1

        if self.curr_end == StreamAggr.GC_SIZE:
            self.garbage_collection()

    def garbage_collection(self):
        self.times[:self.curr_end-self.prev_start] = self.times[self.prev_start:self.curr_end]
        self.values[:self.curr_end-self.prev_start] = self.values[self.prev_start:self.curr_end]
        self.curr_end -= self.prev_start
        self.prev_end -= self.prev_start
        self.prev_end -= self.prev_start
        self.prev_start = 0

    def sum(self):
        return self._sum

    def sum2(self):
        return self._sum2

    def count(self):
        return self._count

    def avg(self):
        return self._sum / self._count

    def var(self):
        return self._sum2 / self._count - self.avg() ** 2

    def std(self):
        return np.sqrt(self.var())
