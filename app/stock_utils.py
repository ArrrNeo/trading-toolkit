#!/usr/bin/python3

# misc imports
import os
import sys
import logging
import datetime
import requests
import pandas as pd
import yfinance as yf
import dateutil.parser
from heapq import nsmallest
import dateutil.relativedelta
from app.models import screener
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
    def getCallOptions(ticker, exp_date):
        try:
            tradier_key = os.environ.get('TRADIER_KEY')
            response = requests.get('https://sandbox.tradier.com/v1/markets/options/chains',
                                params={'symbol': ticker, 'expiration': exp_date, 'greeks': 'true'},
                                headers={'Authorization': 'Bearer ' + tradier_key, 'Accept': 'application/json'}).json()
            return [x for x in response['options']['option'] if x['option_type'] == 'call']
        except Exception as e:
            return []
    
    @staticmethod
    # get stock info from yahoo finance
    def getOptionsDate(ticker):
        try:
            tradier_key = os.environ.get('TRADIER_KEY')
            response = requests.get('https://sandbox.tradier.com/v1/markets/options/expirations',
                                    params={'symbol': ticker, 'includeAllRoots': 'true', 'strikes': 'true'},
                                    headers={'Authorization': 'Bearer ' + tradier_key, 'Accept': 'application/json'}).json()
            return [x['date'] for x in response['expirations']['expiration']]
        except Exception as e:
            return []
    
    @staticmethod
    # get info for debit spread chart
    def getDebitSpreads(ticker, option_date, num_strikes, log_scale, min_profit_pc):
        ctx          = {}
        calculations = []
        curr_price   = StockUtils.getCurrentPrice(ticker)
        data = StockUtils.getCallOptions(ticker, option_date)
        data = nsmallest(num_strikes, data, key=lambda x: abs(x['strike'] - curr_price))
        data = sorted(data, key=lambda k: k['strike'])
        for i in range(0, len(data)):
            for j in range(i+1, len(data)):
                entry = {}
                # print ('long: strike: %5.2f, ask: %5.2f, last: %5.2f, short: strike: %5.2f, bid: %5.2f, last: %5.2f' % (data[i]['strike'], data[i]['ask'], data[i]['last'], data[j]['strike'], data[j]['bid'], data[j]['last']))
                if data[i]['ask']:
                    ask = data[i]['ask']
                else:
                    ask = data[i]['last']
                if data[j]['bid']:
                    bid = data[j]['bid']
                else:
                    bid = data[j]['last']
                entry['premium'] = ask - bid
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
    def CoveredCall_helper_func_2(stock, calculations, min_itm_pc, max_itm_pc, min_max_profit_pc, max_days_to_exp):
        symbol = stock['symbol']
        stock_curr_price = stock['price']
        if str(stock_curr_price) == 'nan':
            return

        option_dates = StockUtils.getOptionsDate(symbol)
        for dt in option_dates:
            dtt = datetime.datetime.strptime(dt, "%Y-%m-%d").date()
            currentDate = datetime.date.today()
            # for a given stock ignore optiosn more than 30 days away
            if (dtt - dateutil.relativedelta.relativedelta(days=max_days_to_exp)) > currentDate:
                continue
            try:
                option_chains = StockUtils.getCallOptions(symbol, dt)
                for row in option_chains:
                    # remove invalid option stikes (tradier api is reporting incorrect strikes for some)
                    if row['strike'] % 0.25 != 0:
                        continue
                    # only consider in the money options
                    if row['strike'] > stock_curr_price:
                        continue
                    if row['ask'] == 0 or row['bid'] == 0:
                        call_price = row['last']
                    else:
                        call_price = (row['ask'] + row['bid'])/2
                    itm_percent = ((stock_curr_price - row['strike']) / row['strike']) * 100
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
                    entry['exp_date']       = dt
                    entry['symbol']         = symbol
                    entry['max_profit']     = max_profit
                    entry['call_price']     = call_price
                    entry['strike']         = row['strike']
                    entry['max_profit_pc']  = max_profit_pc
                    entry['effective_cost'] = effective_cost
                    entry['curr_price']     = stock_curr_price
                    calculations.append(entry)
            except Exception as e:
                pass

    @staticmethod
    def CoveredCall_helper_func_1(tickers, calculations, min_itm_pc, max_itm_pc, min_max_profit_pc, max_days_to_exp):
        for stock in tickers:
            StockUtils.CoveredCall_helper_func_2(stock,
                                                 calculations,
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
        # if finviz_price_filter is not "none",
        # then ticker list is generated from finviz library
        # and already match required price filter
        if finviz_price_filter != "none":
            filters.append(finviz_price_filter)

        if finviz_sector_filter != "none":
            filters.append(finviz_sector_filter)

        # if finviz_price_filter or finviz_sector_filter is not "none"
        # then fetch list of tickers from finviz
        if len(filters):
            list_of_tickers = list(Screener(filters=filters, table='Performance', order='price'))
            list_of_tickers = [{'symbol': x['Ticker'], 'price': x['Price']} for x in list_of_tickers]
        else:
            list_of_tickers = screener.objects.all().values()
            # filter db rows, based on price (will also filter out invalid entries)
            list_of_tickers = [x for x in list_of_tickers if x['price'] != 0 and x['price'] >= min_stock_price and x['price'] <= max_stock_price]

        list_of_tickers = [list_of_tickers[i * lst_size:(i + 1) * lst_size] for i in range((len(list_of_tickers) + lst_size - 1) // lst_size )]
        if debug_iterations:
            list_of_tickers = list_of_tickers[:debug_iterations]
        length = len(list_of_tickers)

        for i in range(length):
            StockUtils.CoveredCall_helper_func_1(list_of_tickers[i],
                                                 calculations,
                                                 min_itm_pc,
                                                 max_itm_pc,
                                                 min_max_profit_pc,
                                                 max_days_to_exp)
            if progress_recorder:
                progress_recorder.set_progress(i + 1, length, f'On iteration {i}')

        return calculations

    @staticmethod
    # get basic info for all stock tickers for the purpose of screener
    def populateScreener():
        total_list_of_tickers = NasdaqController(True).getList()
        # identify saved tickers
        saved_stocks = screener.objects.all().values()
        saved_tickers = [x['symbol'] for x in saved_stocks]
        # identify new tickers
        new_tickers = list(set(total_list_of_tickers) - set(saved_tickers))

        # process saved ticekrs: get just price update
        currentDate = datetime.date.today()
        lst_size = 16 # resize ticker list into sublist of following size
        if currentDate.weekday() == 0:
            pastDate = currentDate - dateutil.relativedelta.relativedelta(days=3)
        else:
            pastDate = currentDate - dateutil.relativedelta.relativedelta(days=1)

        print ('processing saved tickers, total_tickers: ' + str(len(saved_tickers)))
        saved_tickers = [saved_tickers[i * lst_size:(i + 1) * lst_size] for i in range((len(saved_tickers) + lst_size - 1) // lst_size )]
        count = 1
        num_itr = len(saved_tickers)
        for tickers in saved_tickers:
            sys.stdout = open(os.devnull, "w")
            data = yf.download(tickers, pastDate, currentDate)
            sys.stdout = sys.__stdout__
            print ("itr %3d of %3d" % (count, num_itr))
            count = count + 1
            for sym in tickers:
                try:
                    curr_price = data.iloc[0]['Close'][sym]
                    screener.objects.update_or_create(symbol=sym, defaults={ 'price': curr_price })
                except Exception as e:
                    continue

        # process new ticekrs: get complete info,
        count = 1
        num_itr = len(new_tickers)
        print ('processing new tickers, total_tickers: ' + str(num_itr))
        for ticker in new_tickers:
            if count % 100 == 0:
                print ("itr %3d of %3d" % (count, num_itr))
            count = count + 1
            try:
                sys.stdout = open(os.devnull, "w")
                tk = yf.Ticker(ticker)
                price = tk.history().tail(1)['Close'].iloc[0]
                sys.stdout = sys.__stdout__
                sector = tk.info['sector']
                industry = tk.info['industry']
                screener.objects.update_or_create(symbol=ticker, defaults={ 'price': price, 'sector': sector, 'industry': industry})
            except Exception as e:
                # mark failed tickers as invalid enties in db so that they are not treated as new again
                screener.objects.update_or_create(symbol=ticker, defaults={ 'price': 0, 'sector': '', 'industry': ''})
                continue
