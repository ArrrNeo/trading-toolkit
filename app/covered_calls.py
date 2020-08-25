import os
import sys
import time
import pprint
import datetime
import numpy as np
from tqdm import tqdm
import yfinance as yf
import multiprocessing
import dateutil.relativedelta
from app.stocklist import NasdaqController
from joblib import Parallel, delayed, parallel_backend

class CoveredCalls:
    def __init__(self, min_stock_price=0, max_stock_price=5, min_itm_pc=0, max_itm_pc=50, min_max_profit_pc=5, max_days_to_exp=30):
        self.MIN_STOCK_PRICE = min_stock_price
        self.MAX_STOCK_PRICE = max_stock_price
        self.MIN_ITM_PERCENT = min_itm_pc
        self.MAX_ITM_PERCENT = max_itm_pc
        self.MIN_MAX_PROFIT_PERCENT = min_max_profit_pc
        self.MAX_DAYS_TO_EXP = max_days_to_exp

    def getData(self, tickers, calculations):
        currentDate = datetime.date.today()
        if currentDate.weekday() == 0:
            pastDate = currentDate - dateutil.relativedelta.relativedelta(days=3)
        else:
            pastDate = currentDate - dateutil.relativedelta.relativedelta(days=1)
        sys.stdout = open(os.devnull, "w")
        data = yf.download(tickers, pastDate, currentDate)
        sys.stdout = sys.__stdout__
        for sym in tickers:
            # filter out stocks based on price
            try:
                stock_curr_price = data.iloc[0]['Close'][sym]

                if str(stock_curr_price) == 'nan':
                    continue

                if stock_curr_price < self.MIN_STOCK_PRICE or stock_curr_price > self.MAX_STOCK_PRICE:
                    continue
            except Exception as e:
                continue

            # filter out stocks if it does not have options
            obj = yf.Ticker(sym)
            try:
                option_dates = obj.options
            except Exception as e:
                continue

            for dt in option_dates:
                dtt = datetime.datetime.strptime(dt, "%Y-%m-%d").date()
                currentDate = datetime.date.today()
                # for a given stock ignore optiosn more than 30 days away
                if (dtt - dateutil.relativedelta.relativedelta(days=self.MAX_DAYS_TO_EXP)) > currentDate:
                    continue
                try:
                    option_chains = obj.option_chain(dt).calls[['strike', 'lastPrice', 'bid', 'ask', 'volume', 'openInterest', 'impliedVolatility', 'inTheMoney']]
                    # only consider in the money options
                    option_chains = option_chains[option_chains['inTheMoney'] == True]
                    for index, row in option_chains.iterrows():
                        call_price = row['lastPrice']
                        itm_percent = ((stock_curr_price - row['strike']) / row['strike']) * 100
                        if row['bid'] != 0 or row['ask'] != 0:
                            call_price = (row['bid'] + row['ask']) / 2
                        effective_cost = stock_curr_price - call_price
                        max_profit = row['strike'] - effective_cost
                        max_profit_pc = (max_profit / effective_cost) *  100
                        # filter based on in the money percentage
                        if itm_percent < self.MIN_ITM_PERCENT or itm_percent > self.MAX_ITM_PERCENT:
                            continue

                        # filter based on max profit percentage
                        if max_profit_pc < self.MIN_MAX_PROFIT_PERCENT:
                            continue

                        # append this to final list
                        entry = {}
                        entry['symbol'] = sym
                        entry['exp_date'] = dt
                        entry['strike'] = row['strike']
                        entry['max_profit'] = max_profit
                        entry['call_price'] = call_price
                        entry['curr_price'] = stock_curr_price
                        entry['max_profit_pc'] = max_profit_pc
                        entry['effective_cost'] = effective_cost
                        # print (entry)
                        calculations.append(entry)
                except Exception as e:
                    pass

    def main_func(self):
        StocksController = NasdaqController(True)
        list_of_tickers = StocksController.getList()
        lst_size = 8
        list_of_tickers = [list_of_tickers[i * lst_size:(i + 1) * lst_size] for i in range((len(list_of_tickers) + lst_size - 1) // lst_size )]
        start_time = time.time()
        manager = multiprocessing.Manager()
        calculations = manager.list()
        with parallel_backend('loky', n_jobs=multiprocessing.cpu_count() * 2):
            Parallel()(delayed(self.getData)(x, calculations) for x in tqdm(list_of_tickers))

        print("--- this took %s seconds to run ---" % (time.time() - start_time))
        return calculations
