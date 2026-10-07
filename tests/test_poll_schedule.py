import unittest
from trading_bot.main import next_cycle_delay


class PollScheduleTests(unittest.TestCase):
    def test_network_duration_does_not_accumulate_phase_drift(self):
        # Different request durations all lead to the same next polling phase.
        for now in (1501.1, 1502.8, 1515.0, 1799.9):
            self.assertAlmostEqual(now + next_cycle_delay(300,0,0,now),1801)

    def test_server_clock_offset_and_boundary_use_next_bucket(self):
        self.assertAlmostEqual(next_cycle_delay(300,2000,0,1500),299)
        self.assertAlmostEqual(next_cycle_delay(300,0,0,1800),301)

    def test_failure_backoff_preserves_phase_and_is_bounded(self):
        self.assertEqual(next_cycle_delay(300,0,1,1502),599)
        self.assertEqual(next_cycle_delay(300,0,3,1502),2399)
        self.assertEqual(next_cycle_delay(1000,0,10,1502),3600)


if __name__=='__main__': unittest.main()
