#!/usr/bin/python3

# misc imports
import os
import sys
import time
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
from yahoo_earnings_calendar import YahooEarningsCalendar
from tzlocal import get_localzone

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
    # get info for covered call chart
    def SellOptions(tickers,
                    max_days_to_exp,  # filter: number of days to exp
                    min_profit_pc,    # filter: profit to collatral percentage
                    progress_recorder=None):
        print (tickers)
        print (max_days_to_exp)
        print (min_profit_pc)
        print (progress_recorder)
        calculations = []
        num_sym = len(tickers)
        ctr = 0
        for symbol in tickers:
            StockUtils.SellOptions_helper_func_1(symbol,
                                                 max_days_to_exp,
                                                 min_profit_pc,
                                                 calculations)
            if progress_recorder:
                progress_recorder.set_progress(ctr + 1, num_sym, f'On iteration {ctr}')
            ctr = ctr + 1
        return calculations

    @staticmethod
    def SellOptions_helper_func_1(symbol,
                                  max_days_to_exp,  # filter: number of days to exp
                                  min_profit_pc,    # filter: profit to collatral percentage
                                  calculations):
        curr_price = StockUtils.getCurrentPrice(symbol)
        if curr_price == 0:
            return

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
            option_chains = [x for x in option_chains if x['strike'] % 0.25 == 0]
            for row in option_chains:
                entry = {}
                if row['bid'] == 0:
                    premium = row['last']
                else:
                    premium = row['bid']
                if not premium:
                    continue
                strike = row['strike']
                if row['option_type'] == 'call':
                    entry = StockUtils.ProcessSellCall(strike, curr_price, premium, min_profit_pc, dte)
                elif row['option_type'] == 'put':
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

    @staticmethod
    def lotto_calls(ctx, progress_recorder):
        result             = []
        min_iv             = ctx['min_iv']
        max_iv             = ctx['max_iv']
        min_dte            = ctx['min_dte']
        max_dte            = ctx['max_dte']
        iv_flag            = ctx['iv_flag']
        # min_delta          = ctx['min_delta']
        # max_delta          = ctx['max_delta']
        # delta_flag         = ctx['delta_flag']
        max_otm            = ctx['max_otm']
        max_premium        = ctx['max_premium']
        minMarketCap       = ctx['minMarketCap']
        post_er_jump_pc    = ctx['post_er_jump_pc']
        sector_selected    = ctx['sector_selected']
        # pre_er_run_up_pc   = ctx['pre_er_run_up_pc']
        industry_selected  = ctx['industry_selected']
        post_er_jump_flag  = ctx['post_er_jump_flag']
        # pre_er_run_up_flag = ctx['pre_er_run_up_flag']
        # pre_er_run_up_days = ctx['pre_er_run_up_days']

        tickers_db = screener.objects.all().values()
        if sector_selected != 'none':
            tickers_db = [x for x in tickers_db if x['sector'] == sector_selected]
        if industry_selected != 'none':
            tickers_db = [x for x in tickers_db if x['industry'] == industry_selected]
        tickers_db = [x for x in tickers_db if x['marketCap'] >= minMarketCap]
        currentDate  = datetime.date.today()
        min_exp_date = currentDate + dateutil.relativedelta.relativedelta(days=min_dte)
        max_exp_date = currentDate + dateutil.relativedelta.relativedelta(days=max_dte)
        ctr = 0
        num_sym = len(tickers_db)
        for stocks in tickers_db:
            progress_recorder.set_progress(ctr + 1, num_sym, f'On iteration {ctr}')
            ctr = ctr + 1
            er_date=stocks['mostRecentER']
            if not er_date:
                continue

            if er_date.weekday() > 4:
                print ('ER on weekend for %s: %s, skipped.' % (stocks['symbol'], str(er_date)))
                continue

            local_time = stocks['mostRecentER'].astimezone(get_localzone())

            # find before open or after close
            if local_time.hour < 12:
                before_open = True
            else:
                before_open = False

            date_from = er_date - dateutil.relativedelta.relativedelta(days=3)
            date_to = er_date + dateutil.relativedelta.relativedelta(days=4)
            sys.stdout = open(os.devnull, "w")
            data = yf.download(stocks['symbol'], date_from, date_to)
            sys.stdout = sys.__stdout__
            er_idx = data.index.get_loc(str(er_date.date()))
            if before_open == True:
                p_start = data['Close'].iloc[er_idx - 1]
                p_end = data['Close'].iloc[er_idx]
            else:
                p_start = data['Close'].iloc[er_idx]
                p_end = data['Close'].iloc[er_idx + 1]

            p_pc_move = ((p_end - p_start)/p_start) * 100

            if post_er_jump_flag == True and p_pc_move < post_er_jump_pc:
                continue

            symbol = stocks['symbol']
            stocks['p_end'] = p_end
            stocks['p_start'] = p_start
            stocks['p_pc_move'] = p_pc_move
            curr_price = StockUtils.getCurrentPrice(symbol)
            option_dates = StockUtils.getOptionsDate(symbol)
            for exp_date in option_dates:
                dtt = datetime.datetime.strptime(exp_date, "%Y-%m-%d").date()
                if dtt > max_exp_date or dtt < min_exp_date:
                    continue
                dte = (dtt - currentDate).days
                option_chains = StockUtils.getCallOptions(symbol, exp_date)
                for item in option_chains:
                    try:
                        if item['strike'] < curr_price:
                            continue
                        if item['strike'] > ((curr_price * (100 + max_otm))/100):
                            continue
                        if item['strike'] % 0.25 != 0:
                            continue
                        if iv_flag == True and item['greeks']['mid_iv'] < (min_iv/100) and item['greeks']['mid_iv'] > (max_iv/100):
                            continue
                        premium = (item['bid'] + item['ask'])/2
                        if premium > max_premium:
                            continue
                        item['premium'] = premium
                        item['curr_price'] = curr_price
                        item['prev_er_surprise'] = stocks['epsSurprisePC']
                        item['prev_er_jump'] = p_pc_move
                        item['iv'] = item['greeks']['mid_iv']
                        item['delta'] = item['greeks']['delta']
                        item['mostRecentER'] = stocks['mostRecentER']
                        item['nextER'] = stocks['nextER']
                        result.append(item)
                    except Exception as e:
                        print ('exception: ' + str(e) + ' for ' + str(item))
                        pass

        return result

    @staticmethod
    def PopulateEarningDate(num_days):
        yec = YahooEarningsCalendar()
        date_to = datetime.date.today()
        date_from = date_to - dateutil.relativedelta.relativedelta(days=num_days)
        ERs = yec.earnings_between(date_from, date_to)
        ERs = [{k: item[k] for k in ('ticker', 'startdatetime', 'epsestimate', 'epsactual', 'epssurprisepct')} for item in ERs]
        for er in ERs:
            screener.objects.update_or_create(symbol=er['ticker'], defaults={
                                                                        'epsActual'     : er['epsactual'],
                                                                        'epsEstimate'   : er['epsestimate'],
                                                                        'mostRecentER'  : er['startdatetime'],
                                                                        'epsSurprisePC' : er['epssurprisepct']
                                                                    })

    @staticmethod
    # get new tickers data
    def NewTickerScreenerUpdate(new_tickers):
        count = 1
        num_itr = len(new_tickers)
        print ('processing new tickers, total_tickers: ' + str(num_itr))
        for ticker in new_tickers:
            sector = ''
            industry = ''
            marketCap = 0
            options_available = False
            price = 0

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
                marketCap = int(tk.info['marketCap']/1000)

                if sector == '' or industry == '' or marketCap == 0:
                    continue

                if tk.options:
                    options_available = True
            except Exception as e:
                pass

            screener.objects.update_or_create(symbol=ticker, defaults={
                                                                        'price': price,
                                                                        'sector': sector,
                                                                        'industry': industry,
                                                                        'marketCap': marketCap,
                                                                        'options': options_available
                                                                    })

    @staticmethod
    # get new tickers data and price update for current
    def DailyScreenerUpdate():
        print ('DailyScreenerUpdate')
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
        # now parse new tickers
        StockUtils.NewTickerScreenerUpdate(new_tickers)

    @staticmethod
    # fields that needs weekly update
    def WeeklyScreenerUpdate():
        print ('WeeklyScreenerUpdate')
        # fetch list of ERs in last 1 week. since this task is run weely
        StockUtils.PopulateEarningDate(7)

        saved_stocks = screener.objects.all().values()
        saved_tickers = [x['symbol'] for x in saved_stocks]
        count = 1
        num_itr = len(saved_tickers)
        for ticker in saved_tickers:
            marketCap = 0
            options_available = False
            print ("itr %3d of %3d" % (count, num_itr))
            count = count + 1
            try:
                tk = yf.Ticker(ticker)
                marketCap = int(tk.info['marketCap']/1000)
                if tk.options:
                    options_available = True
            except Exception as e:
                print (e)
            screener.objects.update_or_create(symbol=ticker, defaults={ 'options': options_available, 'marketCap': marketCap })

    @staticmethod
    # supposed to be called manually
    def OneTimeUpdate(num_days):
        count = 1
        print ('OneTimeUpdate')
        yec = YahooEarningsCalendar()
        date_from = datetime.date.today()
        date_to = date_from + dateutil.relativedelta.relativedelta(days=num_days)
        ERs = yec.earnings_between(date_from, date_to)
        ERs = [{k: item[k] for k in ('ticker', 'startdatetime')} for item in ERs]
        num_itr = len(ERs)
        for er in ERs:
            screener.objects.update_or_create(symbol=er['ticker'], defaults={ 'nextER' : er['startdatetime'] })
            print ("itr %3d of %3d" % (count, num_itr))
            count = count + 1
