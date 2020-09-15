# standard imports
from time import sleep

# app imports
from app.stock_utils import StockUtils

# celery imports
from celery import shared_task
from celery.decorators import periodic_task
from celery_progress.backend import ProgressRecorder
from datetime import timedelta
from app.stock_utils import StockUtils
from app.models import screener

@periodic_task(run_every=timedelta(hours=12), name="periodic_task_populate_screener", ignore_result=True)
def populate_screener():
    print ('populate_screener')
    StockUtils.populateScreener()

@shared_task(bind=True)
def update_screener(self, duration):
    print ('update_screener')
    StockUtils.updateScreener()

@shared_task(bind=True)
def go_to_sleep(self, duration):
    progress_recorder = ProgressRecorder(self)
    for i in range(5):
        sleep(duration)
        progress_recorder.set_progress(i + 1, 5, f'On iteration {i}')
    return {'status': 'Done'}

@shared_task(bind=True)
def asyn_cc_chart(self,
                  min_stock_price,
                  max_stock_price,
                  min_itm_pc,
                  max_itm_pc,
                  min_max_profit_pc,
                  sector_filter,
                  industry_filter,
                  max_days_to_exp,
                  debug_iterations):
    progress_recorder = ProgressRecorder(self)
    calculations = StockUtils.getCoveredCall(min_stock_price=min_stock_price,
                                             max_stock_price=max_stock_price,
                                             min_itm_pc=min_itm_pc,
                                             max_itm_pc=max_itm_pc,
                                             min_max_profit_pc=min_max_profit_pc,
                                             sector_filter=sector_filter,
                                             industry_filter=industry_filter,
                                             max_days_to_exp=max_days_to_exp,
                                             progress_recorder=progress_recorder,
                                             debug_iterations=debug_iterations)
    ctx                         = {}
    ctx['status']               = 'Done'
    ctx['y_axis']               = 'symbol'
    ctx['min_itm_pc']           = min_itm_pc
    ctx['max_itm_pc']           = max_itm_pc
    ctx['table']                = calculations
    ctx['min_stock_price']      = min_stock_price
    ctx['max_stock_price']      = max_stock_price
    ctx['max_days_to_exp']      = max_days_to_exp
    ctx['min_max_profit_pc']    = min_max_profit_pc
    ctx['x_axis']               = 'max_profit_percentage'
    ctx['symbol']               = [ entry['symbol']         for entry in calculations]

    lst_of_unique = list(set(ctx['symbol']))
    for item in calculations:
        # x will be index of symbol in list of unique symbols
        symbol = item['symbol']
        x = lst_of_unique.index(symbol)
        item.update( { 'x': x } )
    ctx['x']                    = [ entry['x']              for entry in calculations]

    ctx['strike']               = [ entry['strike']         for entry in calculations]
    ctx['exp_date']             = [ entry['exp_date']       for entry in calculations]
    ctx['max_profit']           = [ entry['max_profit']     for entry in calculations]
    ctx['call_price']           = [ entry['call_price']     for entry in calculations]
    ctx['curr_price']           = [ entry['curr_price']     for entry in calculations]
    ctx['max_profit_pc']        = [ entry['max_profit_pc']  for entry in calculations]
    ctx['effective_cost']       = [ entry['effective_cost'] for entry in calculations]

    tickers = screener.objects.all().values()
    sector_options = list(set([x['sector'] for x in tickers]))
    sector_options.remove('')
    industry_options = list(set([x['industry'] for x in tickers]))
    industry_options.remove('')
    ctx['sector_options']       = sector_options
    ctx['industry_options']     = industry_options
    ctx['sector_filter']        = sector_filter
    ctx['industry_filter']      = industry_filter

    return ctx