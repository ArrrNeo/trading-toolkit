#!/usr/bin/python3

# misc imports
import logging
import pandas as pd
import yfinance as yf
import dateutil.parser
import dateutil.relativedelta

LOG_FILENAME = 'error.log'
logging.basicConfig(filename=LOG_FILENAME,level=logging.ERROR)

class StockUtils():
    @staticmethod
    def getHistoryData(tickers, date_from, date_to):
        return yf.download(tickers, date_from, date_to)

    @staticmethod
    def get_nxt_mkt_day(curr_date, direction, history_data):
        days = 0
        delta = dateutil.relativedelta.relativedelta(days=1)
        ret_date = curr_date + (direction * delta)
        while True:
            if StockUtils.is_market_holiday(ret_date, history_data):
                ret_date = ret_date + (direction * delta)
                days = days + 1
            else:
                break
            if days >= 14:
                logging.error("more than 2 weeks and prev day cannot be found")
                ret_date = curr_date
                break
        return ret_date

    @staticmethod
    def is_market_holiday(curr_date, history_data):
        try:
            data = history_data.loc[str(curr_date)]['Close']['AAPL']
            return False
        except Exception as e:
            return True

    @staticmethod
    # will return the value of specifc mix of stocks at specified date
    def getHistoricValue(portfolio, when, history_data):
        value = 0
        if not portfolio:
            return 0
        for ticker in portfolio.keys():
            if not portfolio[ticker]['total_quantity']:
                continue
            # todo: check why does str(when) works and without str does not work
            if str(history_data.loc[str(when)]['Close'][ticker]) == 'nan':
                logging.error(ticker + ' ' + str(when) + ' data not available in history_data (from yfinance.download)')
                value = value + (portfolio[ticker]['average_price'] * portfolio[ticker]['total_quantity'])
            else:
                value = value + (history_data.loc[str(when)]['Close'][ticker] * portfolio[ticker]['total_quantity'])
        return value

    @staticmethod
    # will return the value of specifc mix of stocks at specified date
    def getUnRealizedProfitLoss(portfolio, when):
        value = 0
        # TBD
        return value

    @staticmethod
    # get stock info from yahoo finance
    def getStockInfo(ticker):
        data = yf.Ticker(ticker)
        return data.info

    @staticmethod
    # get stock info from yahoo finance
    def getOptions(ticker, date):
        obj = yf.Ticker(ticker)
        data = obj.option_chain(date).calls[['ask', 'bid', 'strike']]
        return data.to_dict('records')
    
    @staticmethod
    # get stock info from yahoo finance
    def getOptionsDate(ticker):
        return yf.Ticker(ticker).options
