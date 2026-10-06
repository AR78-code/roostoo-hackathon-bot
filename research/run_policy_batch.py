"""Batch 02: breakout policies and volatility-aware target allocation."""
import run_batch

run_batch.CANDIDATES = [
    ('breakout_12h', {'strategy':'breakout','fast_window':144,'slow_window':576,'signal_threshold':0}, 'Buy new 12-hour highs, exit 6-hour lows; fewer SMA crossing assumptions'),
    ('breakout_1d', {'strategy':'breakout','fast_window':288,'slow_window':1152,'signal_threshold':0}, 'Daily breakout, half-day exit'),
    ('breakout_1d_001', {'strategy':'breakout','fast_window':288,'slow_window':1152,'signal_threshold':.001}, 'Nearby daily breakout entry buffer'),
    ('breakout_2d', {'strategy':'breakout','fast_window':576,'slow_window':2304,'signal_threshold':0}, 'Two-day breakout, one-day exit'),
    ('trend_12h_2d_vol01', {'fast_window':144,'slow_window':576,'signal_threshold':.006,'volatility_target':.01}, 'Reduce allocation when realized daily volatility exceeds 1%'),
    ('trend_1d_4d_vol01', {'fast_window':288,'slow_window':1152,'signal_threshold':.006,'volatility_target':.01}, 'Daily trend with conservative volatility sizing'),
    ('trend_1d_4d_vol02', {'fast_window':288,'slow_window':1152,'signal_threshold':.006,'volatility_target':.02}, 'Nearby volatility target: 2%'),
    ('breakout_1d_vol01', {'strategy':'breakout','fast_window':288,'slow_window':1152,'signal_threshold':0,'volatility_target':.01}, 'Daily breakout with reduced high-volatility exposure'),
]

if __name__=='__main__':
    run_batch.main()
