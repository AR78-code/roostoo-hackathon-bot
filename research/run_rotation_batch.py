"""Batch06: fixed relative-strength rules; same signal code in live and replay."""
import run_batch

run_batch.CANDIDATES=[
    ('rotation_1d_4d',{'strategy':'rotation','fast_window':288,'slow_window':1152,'signal_threshold':.006},'Daily relative strength within a four-day positive trend'),
    ('rotation_1d_8d',{'strategy':'rotation','fast_window':288,'slow_window':2304,'signal_threshold':.006},'Daily relative strength with a longer trend filter'),
    ('rotation_2d_8d',{'strategy':'rotation','fast_window':576,'slow_window':2304,'signal_threshold':.006},'Two-day relative strength reduces short-horizon ranking changes'),
    ('rotation_4d_8d',{'strategy':'rotation','fast_window':1152,'slow_window':2304,'signal_threshold':.006},'Four-day relative strength, eight-day positive trend'),
    ('rotation_1d_4d_vol01',{'strategy':'rotation','fast_window':288,'slow_window':1152,'signal_threshold':.006,'volatility_target':.01},'Daily rotation with reduced allocation during high volatility'),
    ('rotation_2d_8d_vol01',{'strategy':'rotation','fast_window':576,'slow_window':2304,'signal_threshold':.006,'volatility_target':.01},'Slower rotation with conservative volatility sizing'),
]

if __name__=='__main__':run_batch.main()
