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
from app.stocklist import NasdaqController
from celery_progress.backend import ProgressRecorder

LOG_FILENAME = 'error.log'
logging.basicConfig(filename=LOG_FILENAME,level=logging.ERROR)

class StockUtils():
    @staticmethod
    # get stock info from yahoo finance
    def getCurrentPrice(ticker):
        try:
            return yf.Ticker(ticker).history().tail(1)['Close'].iloc[0]
        except Exception as e:
            return 0

    @staticmethod
    # get stock info from yahoo finance
    def getOptions(ticker, exp_date):
        try:
            tradier_key = os.environ.get('TRADIER_KEY')
            response = requests.get('https://sandbox.tradier.com/v1/markets/options/chains',
                                params={'symbol': ticker, 'expiration': exp_date, 'greeks': 'true'},
                                headers={'Authorization': 'Bearer ' + tradier_key, 'Accept': 'application/json'}).json()
            return response['options']['option']
        except Exception as e:
            return []

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
    def getPutOptions(ticker, exp_date):
        try:
            tradier_key = os.environ.get('TRADIER_KEY')
            response = requests.get('https://sandbox.tradier.com/v1/markets/options/chains',
                                params={'symbol': ticker, 'expiration': exp_date, 'greeks': 'true'},
                                headers={'Authorization': 'Bearer ' + tradier_key, 'Accept': 'application/json'}).json()
            return [x for x in response['options']['option'] if x['option_type'] == 'put']
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
                # find if options are available for ticker
                try:
                    opt_dates = tk.options
                    if opt_dates:
                        options = True
                    else:
                        options = False
                except Exception as e:
                    options = False
                screener.objects.update_or_create(symbol=ticker, defaults={ 'price': price, 'sector': sector, 'industry': industry, 'options': options})
            except Exception as e:
                # mark failed tickers as invalid enties in db so that they are not treated as new again
                screener.objects.update_or_create(symbol=ticker, defaults={ 'price': 0, 'sector': '', 'industry': '', 'options': False})
                continue

    @staticmethod
    # place-holder function to update table new field
    def updateScreener():
        print ('updateScreener')
        saved_stocks = screener.objects.all().values()
        saved_tickers = [x['symbol'] for x in saved_stocks]
        count = 1
        num_itr = len(saved_tickers)
        for ticker in saved_tickers:
            print ("itr %3d of %3d" % (count, num_itr))
            count = count + 1
            opt_dates = StockUtils.getOptionsDate(ticker)
            if opt_dates:
                screener.objects.update_or_create(symbol=ticker, defaults={ 'options': True })
            else:
                screener.objects.update_or_create(symbol=ticker, defaults={ 'options': False })
        return

    @staticmethod
    # get info for covered call chart
    def SellOptions(tickers,
                    sell_calls,       # filter: should calls be considered
                    sell_puts,        # filter: should puts be considered
                    max_days_to_exp,  # filter: number of days to exp
                    min_strike_pc,    # filter: percentage min strike is away from current price
                    max_strike_pc,    # filter: percentage max strike is away from current price
                    min_profit_pc,    # filter: profit to collatral percentage
                    progress_recorder=None):
        calculations = []
        num_sym = len(tickers)
        ctr = 0
        for symbol in tickers:
            StockUtils.SellOptions_helper_func_1(symbol,
                                                 sell_calls,
                                                 sell_puts,
                                                 max_days_to_exp,
                                                 min_strike_pc,
                                                 max_strike_pc,
                                                 min_profit_pc,
                                                 calculations)
            if progress_recorder:
                progress_recorder.set_progress(ctr + 1, num_sym, f'On iteration {ctr}')
            ctr = ctr + 1
        return calculations

    @staticmethod
    def SellOptions_helper_func_1(symbol,
                                  sell_calls,       # filter: should calls be considered
                                  sell_puts,        # filter: should puts be considered
                                  max_days_to_exp,  # filter: number of days to exp
                                  min_strike_pc,    # filter: percentage min strike is away from current price
                                  max_strike_pc,    # filter: percentage max strike is away from current price
                                  min_profit_pc,    # filter: profit to collatral percentage
                                  calculations):
        curr_price = StockUtils.getCurrentPrice(symbol)
        if curr_price == 0:
            return

        min_strike = (curr_price * (100 - min_strike_pc) / 100)
        max_strike = (curr_price * (100 + max_strike_pc) / 100)

        currentDate  = datetime.date.today()
        max_exp_date = currentDate + dateutil.relativedelta.relativedelta(days=max_days_to_exp)

        option_dates = StockUtils.getOptionsDate(symbol)
        for exp_date in option_dates:
            dtt = datetime.datetime.strptime(exp_date, "%Y-%m-%d").date()
            # for a given stock ignore options more than 30 days away
            if dtt > max_exp_date:
                continue
            dte = (dtt - currentDate).days
            # get all options
            option_chains = StockUtils.getOptions(symbol, exp_date)
            # filter by min/max strike price, invalid option stikes (tradier api is reporting incorrect strikes for some)
            option_chains = [x for x in option_chains if x['strike'] % 0.25 == 0 and x['strike'] >= min_strike and x['strike'] <= max_strike ]
            for row in option_chains:
                entry = {}
                if row['bid'] == 0:
                    premium = row['last']
                else:
                    premium = row['bid']
                if not premium:
                    continue
                strike = row['strike']
                if sell_calls and row['option_type'] == 'call':
                    entry = StockUtils.ProcessSellCall(strike, curr_price, premium, min_profit_pc, dte)
                elif sell_puts and row['option_type'] == 'put':
                    entry = StockUtils.ProcessSellPut(strike, curr_price, premium, min_profit_pc, dte)
                if not entry:
                    continue
                StockUtils.PopulateGreeks(entry, row)
                # append this to final list
                entry['dte']      = dte
                entry['symbol']   = symbol
                entry['exp_date'] = exp_date
                calculations.append(entry)

    @staticmethod
    def PopulateGreeks(entry, row):
        try:
            entry['delta'] = row['greeks']['delta']
            entry['theta'] = row['greeks']['theta']
            entry['iv']    = row['greeks']['mid_iv'] * 100
        except Exception as e:
            entry['delta'] = 0
            entry['theta'] = 0
            entry['iv']    = 0

    @staticmethod
    def ProcessSellCall(strike, curr_price, premium, min_profit_pc, dte):
        entry = {}
        if dte == 0:
            dte = 1
        try:
            collatral = curr_price

            itm_percent = ((curr_price - strike) / curr_price) * 100
            ownership_cost = curr_price - premium

            # profit if stock price remains the same
            if strike < curr_price:
                profit = strike - ownership_cost
            else:
                profit = premium

            profit_pc = (profit / collatral) * 100
            if profit_pc < min_profit_pc:
                return {}

            # max profit for selling calls will be strike_price - ownership_cost (when calls are excercised)
            max_profit = strike - ownership_cost
            max_profit_pc = (max_profit / collatral) * 100
            # for selling calls, drop in price of stock by more than premium recvd will lead to loss
            percent_drop_before_loss = (premium / curr_price) * 100

            # annual return of price stays same
            annual_return = (profit_pc / dte) * 365
            # annual return of price goes beyond
            annual_max_return = (max_profit_pc / dte) * 365

            entry['type']                     = 'c'
            entry['strike']                   = strike
            entry['premium']                  = premium
            entry['profit_pc']                = profit_pc
            entry['curr_price']               = curr_price
            entry['itm_percent']              = itm_percent
            entry['annual_return']            = annual_return
            entry['max_profit_pc']            = max_profit_pc
            entry['ownership_cost']           = ownership_cost
            entry['annual_max_return']        = annual_max_return
            entry['percent_drop_before_loss'] = percent_drop_before_loss
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)
        return entry

    @staticmethod
    def ProcessSellPut(strike, curr_price, premium, min_profit_pc, dte):
        entry = {}
        if dte == 0:
            dte = 1
        try:
            collatral = strike

            itm_percent = ((strike - curr_price) / curr_price) * 100
            ownership_cost = strike - premium
            if ownership_cost > curr_price:
                return {}

            # profit if stock price remains the same
            if strike > curr_price:
                profit = curr_price - ownership_cost
            else:
                profit = premium

            profit_pc = (profit / collatral) * 100
            if profit_pc < min_profit_pc:
                return {}

            # max profit for selling puts will be premium (when put expires worthless)
            max_profit = premium
            max_profit_pc = (max_profit / collatral) * 100
            # for selling puts, after price drops beyond ownership cost loss will happen
            percent_drop_before_loss = ((curr_price - ownership_cost) / curr_price) * 100

            # annual return of price stays same
            annual_return = (profit_pc / dte) * 365
            # annual return of price goes beyond
            annual_max_return = (max_profit_pc / dte) * 365

            entry['type']                     = 'p'
            entry['strike']                   = strike
            entry['premium']                  = premium
            entry['profit_pc']                = profit_pc
            entry['curr_price']               = curr_price
            entry['itm_percent']              = itm_percent
            entry['annual_return']            = annual_return
            entry['max_profit_pc']            = max_profit_pc
            entry['ownership_cost']           = ownership_cost
            entry['annual_max_return']        = annual_max_return
            entry['percent_drop_before_loss'] = percent_drop_before_loss
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)
        return entry