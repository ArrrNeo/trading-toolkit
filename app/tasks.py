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

@periodic_task(run_every=timedelta(hours=24), name="populate_screener_daily_task", ignore_result=True)
def populate_screener_daily_task():
    print ('populate_screener_daily_task')
    StockUtils.DailyScreenerUpdate()

@periodic_task(run_every=timedelta(days=7), name="populate_screener_weekly_task", ignore_result=True)
def populate_screener_weekly_task():
    print ('populate_screener_weekly_task')
    StockUtils.WeeklyScreenerUpdate()

@shared_task(bind=False)
def one_time_update():
    print ('one_time_update')
    StockUtils.OneTimeUpdate()


@shared_task(bind=True)
def asyn_sell_options(self,
                      tickers,
                      max_days_to_exp,
                      min_profit_pc,
                      ctx): # this is used for populating html
    progress_recorder = ProgressRecorder(self)
    calculations = StockUtils.SellOptions(tickers=tickers,
                                          max_days_to_exp=max_days_to_exp,
                                          min_profit_pc=min_profit_pc,
                                          progress_recorder=progress_recorder)
    ctx['iv']                       = [ entry['iv']                       for entry in calculations ]
    ctx['dte']                      = [ entry['dte']                      for entry in calculations ]
    ctx['type']                     = [ entry['type']                     for entry in calculations ]
    ctx['delta']                    = [ entry['delta']                    for entry in calculations ]
    ctx['theta']                    = [ entry['theta']                    for entry in calculations ]
    ctx['symbol']                   = [ entry['symbol']                   for entry in calculations ]
    ctx['strike']                   = [ entry['strike']                   for entry in calculations ]
    ctx['premium']                  = [ entry['premium']                  for entry in calculations ]
    ctx['exp_date']                 = [ entry['exp_date']                 for entry in calculations ]
    ctx['profit_pc']                = [ entry['profit_pc']                for entry in calculations ]
    ctx['curr_price']               = [ entry['curr_price']               for entry in calculations ]
    ctx['itm_percent']              = [ entry['itm_percent']              for entry in calculations ]
    ctx['max_profit_pc']            = [ entry['max_profit_pc']            for entry in calculations ]
    ctx['annual_return']            = [ entry['annual_return']            for entry in calculations ]
    ctx['ownership_cost']           = [ entry['ownership_cost']           for entry in calculations ]
    ctx['annual_max_return']        = [ entry['annual_max_return']        for entry in calculations ]
    ctx['percent_drop_before_loss'] = [ entry['percent_drop_before_loss'] for entry in calculations ]
    return ctx

@shared_task(bind=True)
def asyn_lotto_calls(self, ctx):
    progress_recorder = ProgressRecorder(self)
    ctx['table'] = StockUtils.lotto_calls(ctx=ctx, progress_recorder=progress_recorder)
    return ctx
