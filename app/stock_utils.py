#!/usr/bin/python3

# misc imports
import pandas as pd
import yfinance as yf
import dateutil.parser
import dateutil.relativedelta

# db imports
from app.models import stocks_history

class StockUtils():
    @staticmethod
    def getHistoryData(ticker, date_from, date_to):
        if date_from > date_to:
            return []
        data = yf.download(ticker, date_from, date_to)
        data['symbol'] = ticker
        print (data)
        df_records = data.to_dict('index')
        print(df_records)

        for key in df_records.keys():
            obj = stocks_history.objects.filter(date=key).filter(symbol=df_records[key]['symbol'])
            if not obj:
                obj             = stocks_history()
                obj.date        = key
                obj.symbol      = df_records[key]['symbol']
                obj.open_price  = df_records[key]['Open']
                obj.high        = df_records[key]['High']
                obj.low         = df_records[key]['Low']
                obj.close_price = df_records[key]['Close']
                obj.adj_price   = df_records[key]['Adj Close']
                obj.volume      = df_records[key]['Volume']
                obj.save()

        return data

    @staticmethod
    # will return the value of specifc mix of stocks at specified date
    def getHistoricValue(portfolio, when):
        value = 0
        for ticker in portfolio.keys():
            data = yf.download(ticker, when, when + dateutil.relativedelta.relativedelta(days=1))
            try:
                value = value + (data['Open'].iloc[0] * portfolio[ticker])
            except Exception as e:
                print (e)
                print ('failed for fetching: ' + ticker + ' for date: ' + str(when))
                continue
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
