from utils import StreamAggr

import unittest


class TestStreamAggr(unittest.TestCase):
    def test_stream_aggr(self):
        def assert_values(sum, sum2, count, var, std):
            self.assertAlmostEqual(sum, aggr.sum())
            self.assertAlmostEqual(sum2, aggr.sum2())
            self.assertAlmostEqual(count, aggr.count())
            self.assertAlmostEqual(var, aggr.var())
            self.assertAlmostEqual(std, aggr.std())

        times = [0, 1, 2, 3, 4, 5, 6, 9, 10, 12, 18]
        values = [1, 1, 2, -1, 1, 1, 1, 1, 1, 1, 1]
        sums = [1, 2, 4, 3, 4, 4, 4, 3, 3, 3, 1]
        sum2s = [1, 2, 6, 7, 8, 8, 8, 3, 3, 3, 1]
        counts = [1, 2, 3, 4, 5, 5, 5, 3, 3, 3, 1]
        vars = []
        stds = []
        for sum, sum2, count in zip(sums, sum2s, counts):
            vars.append(sum2 / count - (sum / count) ** 2)
            stds.append(vars[-1] ** 0.5)
        aggr = StreamAggr(window_size=5, window_type='ms')
        for time, value, sum, sum2, count, var, std in zip(times, values, sums, sum2s, counts, vars, stds):
            aggr.feed(time, value)
            assert_values(sum, sum2, count, var, std)
