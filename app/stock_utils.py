#!/usr/bin/python3

# misc imports
import os
import sys
import logging
import datetime
import pandas as pd
import yfinance as yf
import dateutil.parser
from heapq import nsmallest
import dateutil.relativedelta
from finviz.screener import Screener
from app.stocklist import NasdaqController
from celery_progress.backend import ProgressRecorder

LOG_FILENAME = 'error.log'
logging.basicConfig(filename=LOG_FILENAME,level=logging.ERROR)

class StockUtils():
    @staticmethod
    # get stock info from yahoo finance
    def getCurrentPrice(ticker):
        return yf.Ticker(ticker).history().tail(1)['Close'].iloc[0]

    @staticmethod
    # get stock info from yahoo finance
    def getOptions(ticker, date):
        obj = yf.Ticker(ticker)
        data = obj.option_chain(date).calls[['strike', 'lastPrice', 'bid', 'ask', 'volume', 'openInterest', 'impliedVolatility', 'inTheMoney']]
        return data.to_dict('records')
    
    @staticmethod
    # get stock info from yahoo finance
    def getOptionsDate(ticker):
        try:
            return list(yf.Ticker(ticker).options)
        except Exception as e:
            return []
    
    @staticmethod
    # get info for debit spread chart
    def getDebitSpreads(ticker, option_date, num_strikes, log_scale, min_profit_pc):
        ctx          = {}
        calculations = []
        curr_price   = StockUtils.getCurrentPrice(ticker)
        data = StockUtils.getOptions(ticker, option_date)
        data = nsmallest(num_strikes, data, key=lambda x: abs(x['strike'] - curr_price))
        data = sorted(data, key=lambda k: k['strike'])
        for i in range(0, len(data)):
            for j in range(i+1, len(data)):
                entry = {}
                if data[i]['ask'] == 0 and data[j]['bid'] == 0:
                    entry['premium'] = data[i]['lastPrice'] - data[j]['lastPrice']
                else:
                    entry['premium'] = data[i]['ask'] - data[j]['bid']
                entry['max_profit'] = (data[j]['strike'] - data[i]['strike']) - entry['premium']
                entry['long_strike'] = data[i]['strike']
                entry['short_strike'] = data[j]['strike']
                entry['trade'] = 'buy: ' + str(entry['long_strike']) + 'c, sell: ' + str(entry['short_strike']) + 'c'
                if entry['premium'] == 0:
                    continue
                entry['distance_from_breakeven'] = ((curr_price - (entry['long_strike'] + entry['premium'])) / curr_price) * 100
                entry['max_profit_pc'] = (entry['max_profit'] / entry['premium']) * 100
                if entry['max_profit_pc'] <= min_profit_pc:
                    continue
                calculations.append(entry)
        calculations = sorted(calculations, key=lambda k: k['max_profit_pc'])

        ctx['ticker']                  = ticker
        ctx['log_scale']               = log_scale
        ctx['curr_price']              = curr_price
        ctx['date']                    = option_date
        ctx['num_strikes']             = num_strikes
        ctx['x_axis']                  = 'long_strike'
        ctx['min_profit_pc']           = min_profit_pc
        ctx['y_axis']                  = 'max_profit_percent'
        ctx['premium']                 = [x['premium']                 for x in calculations]
        ctx['max_profit']              = [x['max_profit']              for x in calculations]
        ctx['long_strike']             = [x['long_strike']             for x in calculations]
        ctx['short_strike']            = [x['short_strike']            for x in calculations]
        ctx['max_profit_pc']           = [x['max_profit_pc']           for x in calculations]
        ctx['distance_from_breakeven'] = [x['distance_from_breakeven'] for x in calculations]
        return ctx

    @staticmethod
    def CoveredCall_helper_func_2(sym, calculations, min_stock_price, max_stock_price, min_itm_pc, max_itm_pc, min_max_profit_pc, max_days_to_exp):
        if min_stock_price != -1 and max_stock_price != -1:
            # filter out stocks based on price
            stock_curr_price = StockUtils.getCurrentPrice(sym)
            if str(stock_curr_price) == 'nan':
                return
            if stock_curr_price < min_stock_price or stock_curr_price > max_stock_price:
                return

        option_dates = StockUtils.getOptionsDate(sym)
        for dt in option_dates:
            dtt = datetime.datetime.strptime(dt, "%Y-%m-%d").date()
            currentDate = datetime.date.today()
            # for a given stock ignore optiosn more than 30 days away
            if (dtt - dateutil.relativedelta.relativedelta(days=max_days_to_exp)) > currentDate:
                continue
            try:
                obj = yf.Ticker(sym)
                option_chains = obj.option_chain(dt).calls[['strike', 'lastPrice', 'bid', 'ask', 'volume', 'openInterest', 'impliedVolatility', 'inTheMoney']]
                # only consider in the money options
                option_chains = option_chains[option_chains['inTheMoney'] == True]
                for index, row in option_chains.iterrows():
                    call_price = row['lastPrice']
                    itm_percent = ((stock_curr_price - row['strike']) / row['strike']) * 100
                    if row['bid'] != 0 or row['ask'] != 0:
                        call_price = (row['bid'] + row['ask']) / 2
                    if str(call_price) == 'nan':
                        continue
                    effective_cost = stock_curr_price - call_price
                    max_profit = row['strike'] - effective_cost
                    max_profit_pc = (max_profit / effective_cost) *  100
                    # filter based on in the money percentage
                    if itm_percent < min_itm_pc or itm_percent > max_itm_pc:
                        continue

                    # filter based on max profit percentage
                    if max_profit_pc < min_max_profit_pc:
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
                    calculations.append(entry)
            except Exception as e:
                pass

    @staticmethod
    def CoveredCall_helper_func_1(tickers, calculations, min_stock_price, max_stock_price, min_itm_pc, max_itm_pc, min_max_profit_pc, max_days_to_exp):
        for sym in tickers:
            StockUtils.CoveredCall_helper_func_2(sym,
                                                 calculations,
                                                 min_stock_price,
                                                 max_stock_price,
                                                 min_itm_pc,
                                                 max_itm_pc,
                                                 min_max_profit_pc,
                                                 max_days_to_exp)

    @staticmethod
    # get info for covered call chart
    def getCoveredCall(min_stock_price=0,
                       max_stock_price=5,
                       min_itm_pc=0,
                       max_itm_pc=50,
                       min_max_profit_pc=5,
                       max_days_to_exp=30,
                       finviz_price_filter="none",
                       finviz_sector_filter="none",
                       progress_recorder=None,
                       debug_iterations=0):
        filters = []
        lst_size = 8 # resize ticker list into sublist of following size
        calculations = []
        # if finviz_price_filter is not "none", then ticker list is generated from
        # finviz library and already match required price filter, hence:
        # set min_stock_price = -1 and set max_stock_price = -1
        if finviz_price_filter != "none":
            min_stock_price = -1
            max_stock_price = -1
            filters.append(finviz_price_filter)

        if finviz_sector_filter != "none":
            filters.append(finviz_sector_filter)

        # if finviz_price_filter or finviz_sector_filter is not "none"
        # then fetch list of tickers from finviz
        if len(filters):
            list_of_tickers = list(Screener(filters=filters, table='Performance', order='price'))
            list_of_tickers = [x['Ticker'] for x in list_of_tickers]
        else:
            StocksController = NasdaqController(True)
            list_of_tickers = StocksController.getList()

        list_of_tickers = [list_of_tickers[i * lst_size:(i + 1) * lst_size] for i in range((len(list_of_tickers) + lst_size - 1) // lst_size )]
        if debug_iterations:
            list_of_tickers = list_of_tickers[:debug_iterations]
        length = len(list_of_tickers)

        for i in range(length):
            StockUtils.CoveredCall_helper_func_1(list_of_tickers[i],
                                                 calculations,
                                                 min_stock_price,
                                                 max_stock_price,
                                                 min_itm_pc,
                                                 max_itm_pc,
                                                 min_max_profit_pc,
                                                 max_days_to_exp)
            if progress_recorder:
                progress_recorder.set_progress(i + 1, length, f'On iteration {i}')

        return calculations
