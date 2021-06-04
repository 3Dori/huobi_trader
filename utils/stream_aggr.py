import numpy as np
from matplotlib import pyplot as plt


class StreamAggr(object):
    TMP_MEM_SIZE = 2 ** 20
    GC_SIZE = 2 ** 20 - 1
    TIME_OFFSET = 0.1

    def __init__(self, window_size, window_type='s', metrics=('bollinger',)):
        self.times = np.zeros(StreamAggr.TMP_MEM_SIZE, dtype=int)
        self.values = np.zeros(StreamAggr.TMP_MEM_SIZE, dtype=float)
        self.prev_start = self.prev_end = 0
        self.curr_start = self.curr_end = 0
        if window_type != 's':
            raise ValueError('window_type must be "s"')
        self.window_size = window_size * (1 if window_type == 's' else 0)
        self.window_type = window_type
        self.metrics = {}
        if metrics is not None:
            metrics = set(metrics)
            for metric in metrics:
                if metric == 'bollinger':
                    self.metrics['ma'] = np.zeros(StreamAggr.TMP_MEM_SIZE, dtype=float)
                    self.metrics['std'] = np.zeros(StreamAggr.TMP_MEM_SIZE, dtype=float)
                else:
                    raise ValueError(f'Unknown metric "{metric}"')
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

        for name, metric in self.metrics.items():
            if name == 'ma':
                metric[self.prev_end] = self.avg()
            elif name == 'std':
                metric[self.prev_end] = self.std()

        if self.curr_end == StreamAggr.GC_SIZE:
            raise MemoryError('OOM')
            # self.garbage_collection()

    def garbage_collection(self):
        self.times[:self.curr_end-self.prev_start] = self.times[self.prev_start:self.curr_end]
        self.values[:self.curr_end-self.prev_start] = self.values[self.prev_start:self.curr_end]
        self.curr_end -= self.prev_start
        self.prev_end -= self.prev_start
        self.prev_end -= self.prev_start
        self.prev_start = 0

    def plot_bollinger(self):
        if self.metrics.get('ma', None) is None or self.metrics.get('std', None) is None:
            raise ValueError('Unable to get ma or std from metrics. '
                             'Consider create the aggregator with metrics="bollinger"')
        times = self.times[:self.curr_end]
        mas = self.metrics['ma'][:self.curr_end]
        stds = self.metrics['std'][:self.curr_end]
        plt.plot(times, mas)
        plt.plot(times, mas + stds*2, '--')
        plt.plot(times, mas - stds*2, '--')
        plt.show()

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
