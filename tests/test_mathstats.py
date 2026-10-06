import math
import random
import statistics
import unittest
from trading_bot.mathstats import population_std


class PopulationDeviationTests(unittest.TestCase):
    def test_matches_reference_for_financial_returns(self):
        rng=random.Random(2026)
        series=[[0]*288,[.0001]*288,[-.03,.02]*144,
                [rng.gauss(0,.004) for _ in range(288)],
                [1e-12+i*1e-15 for i in range(288)]]
        for rows in series:
            self.assertTrue(math.isclose(population_std(rows),statistics.pstdev(rows),rel_tol=1e-12,abs_tol=1e-16))

    def test_rejects_missing_or_nonfinite_values(self):
        for rows in ([],[math.nan],[math.inf],[-math.inf]):
            with self.assertRaises(ValueError):population_std(rows)


if __name__=='__main__':unittest.main()
