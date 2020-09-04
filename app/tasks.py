from time import sleep
from celery import shared_task
from app.stock_utils import StockUtils
from celery_progress.backend import ProgressRecorder

@shared_task(bind=True)
def go_to_sleep(self, duration):
    progress_recorder = ProgressRecorder(self)
    for i in range(5):
        sleep(duration)
        progress_recorder.set_progress(i + 1, 5, f'On iteration {i}')
    return {'status': 'Done'}

@shared_task(bind=True)
def asyn_cc_chart(self, min_stock_price, max_stock_price, min_itm_pc, max_itm_pc, min_max_profit_pc, max_days_to_exp):
    progress_recorder = ProgressRecorder(self)
    calculations = StockUtils.getCoveredCall(progress_recorder,
                                             min_stock_price=min_stock_price,
                                             max_stock_price=max_stock_price,
                                             min_itm_pc=min_itm_pc,
                                             max_itm_pc=max_itm_pc,
                                             min_max_profit_pc=min_max_profit_pc,
                                             max_days_to_exp=max_days_to_exp)
    ctx                      = {}
    ctx['status']            = 'Done'
    ctx['y_axis']            = 'symbol'
    ctx['min_itm_pc']        = min_itm_pc
    ctx['max_itm_pc']        = max_itm_pc
    ctx['table']             = calculations
    ctx['min_stock_price']   = min_stock_price
    ctx['max_stock_price']   = max_stock_price
    ctx['max_days_to_exp']   = max_days_to_exp
    ctx['min_max_profit_pc'] = min_max_profit_pc
    ctx['x_axis']            = 'max_profit_percentage'
    ctx['symbol']            = [ entry['symbol']         for entry in calculations]
    ctx['strike']            = [ entry['strike']         for entry in calculations]
    ctx['exp_date']          = [ entry['exp_date']       for entry in calculations]
    ctx['max_profit']        = [ entry['max_profit']     for entry in calculations]
    ctx['call_price']        = [ entry['call_price']     for entry in calculations]
    ctx['curr_price']        = [ entry['curr_price']     for entry in calculations]
    ctx['max_profit_pc']     = [ entry['max_profit_pc']  for entry in calculations]
    ctx['effective_cost']    = [ entry['effective_cost'] for entry in calculations]
    ctx['effective_cost']    = [ entry['effective_cost'] for entry in calculations]
    return ctx