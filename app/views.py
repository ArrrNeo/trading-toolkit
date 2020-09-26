# -*- encoding: utf-8 -*-
"""
MIT License
Copyright (c) 2019 - present AppSeed.us
"""

import os
import re
import json
from django import template
from django.db.models import Sum
from django.template import loader
from django.http import HttpResponse
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from celery.result import AsyncResult

from app.tasks import asyn_sell_options
from app.stock_utils import StockUtils
from app.models import screener

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
    min_profit_pc = 5
    num_strikes   = 10
    ticker        = 'ROKU'
    log_scale     = False
    option_date   = (StockUtils.getOptionsDate(ticker)[0])

    if request.method == 'POST':
        ticker = request.POST.get('ticker')
        option_date = str(request.POST.get('date'))
        num_strikes = int(request.POST.get('num_strikes'))
        log_scale = bool(request.POST.get('log_scale'))
        min_profit_pc = float(request.POST.get('min_profit_pc'))

    ctx = StockUtils.getDebitSpreads(ticker, option_date, num_strikes, log_scale, min_profit_pc)
    return render(request, 'debit_spread_chart.html', ctx)

def sell_options_result(request):
    task_id = request.GET.get('task_id', None)
    if task_id is not None:
        task = AsyncResult(task_id)
        return render(request, 'sell_options_chart.html', task.result)
    else:
        return HttpResponse('No job id given.')

def db(request):
    table = screener.objects.all()
    return render(request, "db.html", {"table": table})

def sell_options_chart(request):
    ctx                               = {}
    tickers_str                       = 'TSLA'
    calculations                      = []
    sell_calls                        = False
    sell_puts                         = True
    min_price                         = 0
    max_price                         = 0
    min_strike_pc                     = 20
    max_strike_pc                     = 20
    min_profit_pc                     = 1
    max_days_to_exp                   = 30
    sector_selected                   = 'none'
    industry_selected                 = 'none'

    tickers_db = screener.objects.all().values()
    sector_options = list(set([x['sector'] for x in tickers_db if x['options'] == True]))
    sector_options.remove('')
    industry_options = list(set([x['industry'] for x in tickers_db if x['options'] == True]))
    industry_options.remove('')
    sector_options.sort()
    industry_options.sort()

    if request.method == 'POST':
        sell_puts          = bool(request.POST.get('sell_puts'))
        sell_calls         = bool(request.POST.get('sell_calls'))
        min_price          = float(request.POST.get('min_price'))
        max_price          = float(request.POST.get('max_price'))
        min_strike_pc      = float(request.POST.get('min_strike_pc'))
        max_strike_pc      = float(request.POST.get('max_strike_pc'))
        min_profit_pc      = float(request.POST.get('min_profit_pc'))
        max_days_to_exp    = int(request.POST.get('max_days_to_exp'))
        sector_selected    = request.POST.get('sector')
        industry_selected  = request.POST.get('industry')
        tickers_str        = request.POST.get('tickers')

        if sector_selected == 'Select Sector':
            sector_selected = 'none'

        if industry_selected == 'Select Industry':
            industry_selected = 'none'

        tickers = re.split(',| ', tickers_str)
        if '' in tickers:
            tickers.remove('')

        if min_price or max_price or industry_selected != 'none' or sector_selected != 'none':
            if len(tickers_db) and min_price:
                tickers_db = [x for x in tickers_db if x['price'] >= min_price]
            
            if len(tickers_db) and max_price:
                tickers_db = [x for x in tickers_db if x['price'] <= max_price]

            if len(tickers_db) and industry_selected != 'none':
                tickers_db = [x for x in tickers_db if x['industry'] == industry_selected]

            if len(tickers_db) and sector_selected != 'none':
                tickers_db = [x for x in tickers_db if x['sector'] == sector_selected]

            tickers = [x['symbol'] for x in tickers_db]

        ctx['tickers']                  = tickers_str
        ctx['sell_calls']               = sell_calls
        ctx['sell_puts']                = sell_puts
        ctx['min_price']                = min_price
        ctx['max_price']                = max_price
        ctx['min_strike_pc']            = min_strike_pc
        ctx['max_strike_pc']            = max_strike_pc
        ctx['min_profit_pc']            = min_profit_pc
        ctx['max_days_to_exp']          = max_days_to_exp
        ctx['sector_options']           = sector_options
        ctx['industry_options']         = industry_options
        ctx['sector_selected']          = sector_selected
        ctx['industry_selected']        = industry_selected
        task = asyn_sell_options.delay(tickers=tickers,
                                       sell_calls=sell_calls,
                                       sell_puts=sell_puts,
                                       max_days_to_exp=max_days_to_exp,
                                       min_strike_pc=min_strike_pc,
                                       max_strike_pc=max_strike_pc,
                                       min_profit_pc=min_profit_pc,
                                       ctx=ctx)
        return render(request, 'sell_options_progress.html', { 'task_id' : task.task_id })
    else:
        ctx['tickers']                  = tickers_str
        ctx['sell_calls']               = sell_calls
        ctx['sell_puts']                = sell_puts
        ctx['min_price']                = min_price
        ctx['max_price']                = max_price
        ctx['min_strike_pc']            = min_strike_pc
        ctx['max_strike_pc']            = max_strike_pc
        ctx['min_profit_pc']            = min_profit_pc
        ctx['max_days_to_exp']          = max_days_to_exp
        ctx['sector_options']           = sector_options
        ctx['industry_options']         = industry_options
        ctx['sector_selected']          = sector_selected
        ctx['industry_selected']        = industry_selected
        ctx['iv']                       = []
        ctx['dte']                      = []
        ctx['type']                     = []
        ctx['delta']                    = []
        ctx['theta']                    = []
        ctx['symbol']                   = []
        ctx['strike']                   = []
        ctx['premium']                  = []
        ctx['exp_date']                 = []
        ctx['profit_pc']                = []
        ctx['curr_price']               = []
        ctx['itm_percent']              = []
        ctx['max_profit_pc']            = []
        ctx['annual_return']            = []
        ctx['ownership_cost']           = []
        ctx['annual_max_return']        = []
        ctx['percent_drop_before_loss'] = []
        return render(request, 'sell_options_chart.html', ctx)
