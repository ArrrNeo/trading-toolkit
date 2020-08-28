# -*- encoding: utf-8 -*-
"""
MIT License
Copyright (c) 2019 - present AppSeed.us
"""

import os
from django import template
from django.db.models import Sum
from django.template import loader
from django.http import HttpResponse
from django.http import JsonResponse
from app.stock_utils import StockUtils
from app.covered_calls import CoveredCalls
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from heapq import nsmallest

# import pprint
# import datetime
# from datetime import date
# import dateutil.relativedelta

def pages(request):
    context = {}
    # All resource paths end in .html.
    # Pick out the html file name from the url. And load that template.
    print (request.path)
    try:
        load_template = request.path.split('/')[-1]
        print (load_template)
        html_template = loader.get_template( load_template )
        return HttpResponse(html_template.render(context, request))
    except template.TemplateDoesNotExist:
        html_template = loader.get_template( 'page-404.html' )
        return HttpResponse(html_template.render(context, request))
    except:
        html_template = loader.get_template( 'page-500.html' )
        return HttpResponse(html_template.render(context, request))

def debit_spread_chart(request):
    ctx = {}
    ticker = 'ROKU'
    num_strikes = 10
    calculations = []
    min_profit_pc = 5
    log_scale = False
    option_date = (StockUtils.getOptionsDate(ticker)[0])

    if request.method == 'POST':
        ticker = request.POST.get('ticker')
        option_date = str(request.POST.get('date'))
        num_strikes = int(request.POST.get('num_strikes'))
        log_scale = bool(request.POST.get('log_scale'))
        min_profit_pc = int(request.POST.get('min_profit_pc'))

    ctx['ticker'] = ticker
    ctx['date'] = option_date
    ctx['log_scale'] = log_scale
    ctx['num_strikes'] = num_strikes
    ctx['min_profit_pc'] = min_profit_pc

    curr_price = StockUtils.getCurrentPrice(ticker)
    ctx['curr_price'] = curr_price

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
    # for entry in calculations:
    #     print ('trade: %s, premium: %7.2f, max_profit: %7.2f, max_profit_pc: %7.2f' % (entry['trade'], entry['premium'], entry['max_profit'], entry['max_profit_pc']))

    ctx['x_axis']                  = 'long_strike'
    ctx['y_axis']                  = 'max_profit_percent'
    ctx['premium']                 = [x['premium']                 for x in calculations]
    ctx['max_profit']              = [x['max_profit']              for x in calculations]
    ctx['long_strike']             = [x['long_strike']             for x in calculations]
    ctx['short_strike']            = [x['short_strike']            for x in calculations]
    ctx['max_profit_pc']           = [x['max_profit_pc']           for x in calculations]
    ctx['distance_from_breakeven'] = [x['distance_from_breakeven'] for x in calculations]

    return render(request, 'debit_spread_chart.html', ctx)

def covered_calls_chart(request):
    ctx               = {}
    min_stock_price   = 100
    max_stock_price   = 105
    min_itm_pc        = 0
    max_itm_pc        = 50
    min_max_profit_pc = 10
    max_days_to_exp   = 30

    if request.method == 'POST':
        min_stock_price   = int(request.POST.get('min_stock_price'))
        max_stock_price   = int(request.POST.get('max_stock_price'))
        min_itm_pc        = int(request.POST.get('min_itm_pc'))
        max_itm_pc        = int(request.POST.get('max_itm_pc'))
        min_max_profit_pc = int(request.POST.get('min_max_profit_pc'))
        max_days_to_exp   = int(request.POST.get('max_days_to_exp'))

    ctx['min_stock_price']   = min_stock_price
    ctx['max_stock_price']   = max_stock_price
    ctx['min_itm_pc']        = min_itm_pc
    ctx['max_itm_pc']        = max_itm_pc
    ctx['min_max_profit_pc'] = min_max_profit_pc
    ctx['max_days_to_exp']   = max_days_to_exp

    # print (min_stock_price)
    # print (max_stock_price)
    # print (min_itm_pc)
    # print (max_itm_pc)
    # print (min_max_profit_pc)
    # print (max_days_to_exp)

    obj = CoveredCalls(min_stock_price=min_stock_price,
                       max_stock_price=max_stock_price,
                       min_itm_pc=min_itm_pc,
                       max_itm_pc=max_itm_pc,
                       min_max_profit_pc=min_max_profit_pc,
                       max_days_to_exp=max_days_to_exp)
    calculations = obj.main_func()

    # for item in calculations:
    #     print("symbol: %5s, curr_price: %7.2f, call_price: %7.2f, exp: %s, strike: %7.2f, effective_cost: %7.2f, max_profit: %7.2f, max_profit_pc: %7.2f" %
    #           (item['symbol'], item['curr_price'], item['call_price'], item['exp_date'], item['strike'], item['effective_cost'], item['max_profit'], item['max_profit_pc']))
    # print (len(calculations))

    ctx['y_axis']         = 'symbol'
    ctx['x_axis']         = 'max_profit_percentage'
    ctx['symbol']         = [ entry['symbol']         for entry in calculations]
    ctx['strike']         = [ entry['strike']         for entry in calculations]
    ctx['exp_date']       = [ entry['exp_date']       for entry in calculations]
    ctx['max_profit']     = [ entry['max_profit']     for entry in calculations]
    ctx['call_price']     = [ entry['call_price']     for entry in calculations]
    ctx['curr_price']     = [ entry['curr_price']     for entry in calculations]
    ctx['max_profit_pc']  = [ entry['max_profit_pc']  for entry in calculations]
    ctx['effective_cost'] = [ entry['effective_cost'] for entry in calculations]
    # print (ctx['symbol'])
    # print (len(ctx['symbol']))
    ctx['table'] = calculations
    return render(request, 'covered_calls_chart.html', ctx)
