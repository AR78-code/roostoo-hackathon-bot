"""Batch 04: a small fixed family of dips within an established rising trend."""
import run_batch

run_batch.CANDIDATES = [
    ('pullback_6h_2d_005', {'strategy':'pullback','fast_window':72,'slow_window':576,'signal_threshold':.005}, 'Half-percent dip below six-hour mean, positive two-day trend'),
    ('pullback_6h_2d_010', {'strategy':'pullback','fast_window':72,'slow_window':576,'signal_threshold':.010}, 'One-percent dip reduces shallow entries'),
    ('pullback_12h_4d_010', {'strategy':'pullback','fast_window':144,'slow_window':1152,'signal_threshold':.010}, 'Slower mean and longer trend filter'),
    ('pullback_12h_4d_020', {'strategy':'pullback','fast_window':144,'slow_window':1152,'signal_threshold':.020}, 'Two-percent dip requires a larger recovery margin over costs'),
    ('pullback_12h_4d_010_vol01', {'strategy':'pullback','fast_window':144,'slow_window':1152,'signal_threshold':.010,'volatility_target':.01}, 'Reduce exposure during volatile dips'),
    ('pullback_1d_8d_020', {'strategy':'pullback','fast_window':288,'slow_window':2304,'signal_threshold':.020}, 'Daily mean with eight-day trend gate'),
]

if __name__ == '__main__':
    run_batch.main()
