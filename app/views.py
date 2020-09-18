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

from app.tasks import asyn_cc_chart
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

def covered_calls_screener(request):
    ctx                  = {}
    min_itm_pc           = 0
    max_itm_pc           = 50
    max_days_to_exp      = 30
    min_stock_price      = 3
    max_stock_price      = 5
    min_max_profit_pc    = 20

    if request.method == 'POST':
        min_itm_pc            = float(request.POST.get('min_itm_pc'))
        max_itm_pc            = float(request.POST.get('max_itm_pc'))
        max_days_to_exp       = int(request.POST.get('max_days_to_exp'))
        min_max_profit_pc     = float(request.POST.get('min_max_profit_pc'))
        min_stock_price       = float(request.POST.get('min_stock_price'))
        max_stock_price       = float(request.POST.get('max_stock_price'))
        sector_filter         = request.POST.get('sector_filter')
        industry_filter       = request.POST.get('industry_filter')
        if sector_filter == 'Select Sector':
            sector_filter = 'none'
        if industry_filter == 'Select Industry':
            industry_filter = 'none'

        task = asyn_cc_chart.delay(min_stock_price=min_stock_price,
                                   max_stock_price=max_stock_price,
                                   min_itm_pc=min_itm_pc,
                                   max_itm_pc=max_itm_pc,
                                   min_max_profit_pc=min_max_profit_pc,
                                   sector_filter=sector_filter,
                                   industry_filter=industry_filter,
                                   max_days_to_exp=max_days_to_exp,
                                   debug_iterations=0)

        return render(request, 'covered_calls_screener_progress.html', { 'task_id' : task.task_id })
    else:
        tickers = screener.objects.all().values()
        sector_options = list(set([x['sector'] for x in tickers]))
        sector_options.remove('')
        industry_options = list(set([x['industry'] for x in tickers]))
        industry_options.remove('')
        ctx['min_itm_pc']           = min_itm_pc
        ctx['max_itm_pc']           = max_itm_pc
        ctx['min_stock_price']      = min_stock_price
        ctx['max_stock_price']      = max_stock_price
        ctx['max_days_to_exp']      = max_days_to_exp
        ctx['min_max_profit_pc']    = min_max_profit_pc
        ctx['x']                    = []
        ctx['table']                = []
        ctx['symbol']               = []
        ctx['strike']               = []
        ctx['exp_date']             = []
        ctx['max_profit']           = []
        ctx['call_price']           = []
        ctx['curr_price']           = []
        ctx['max_profit_pc']        = []
        ctx['effective_cost']       = []
        ctx['y_axis']               = 'symbol'
        ctx['x_axis']               = 'max_profit_percentage'
        ctx['sector_options']       = sector_options
        ctx['industry_options']     = industry_options
        ctx['sector_filter']        = 'none'
        ctx['industry_filter']      = 'none'
        return render(request, 'covered_calls_screener_results.html', ctx)

def covered_calls_screener_results(request):
    print (request)
    task_id = request.GET.get('task_id', None)
    if task_id is not None:
        task = AsyncResult(task_id)
        return render(request, 'covered_calls_screener_results.html', task.result)
        # return HttpResponse(json.dumps(task.result), content_type='application/json')
    else:
        return HttpResponse('No job id given.')

def db(request):
    table = screener.objects.all()
    return render(request, "db.html", {"table": table})

def covered_calls(request):
    ctx                  = {}
    min_itm_pc           = 0
    max_itm_pc           = 50
    tickers_str          = ''
    calculations         = []
    max_days_to_exp      = 30
    min_max_profit_pc    = 5

    if request.method == 'POST':
        min_itm_pc            = float(request.POST.get('min_itm_pc'))
        max_itm_pc            = float(request.POST.get('max_itm_pc'))
        max_days_to_exp       = int(request.POST.get('max_days_to_exp'))
        min_max_profit_pc     = float(request.POST.get('min_max_profit_pc'))
        tickers_str           = request.POST.get('tickers')
        tickers               = re.split(',| ', tickers_str)
        if '' in tickers:
            tickers.remove('')
        calculations = StockUtils.getCoveredCall(min_stock_price=0,
                                                 max_stock_price=0,
                                                 min_itm_pc=min_itm_pc,
                                                 max_itm_pc=max_itm_pc,
                                                 min_max_profit_pc=min_max_profit_pc,
                                                 sector_filter='none',
                                                 industry_filter='none',
                                                 max_days_to_exp=max_days_to_exp,
                                                 progress_recorder=None,
                                                 debug_iterations=0,
                                                 tickers=tickers)
    print (calculations)
    ctx['table']                = calculations
    ctx['tickers']              = tickers_str
    ctx['min_itm_pc']           = min_itm_pc
    ctx['max_itm_pc']           = max_itm_pc
    ctx['max_days_to_exp']      = max_days_to_exp
    ctx['min_max_profit_pc']    = min_max_profit_pc
    ctx['dte']                  = [ entry['dte']         for entry in calculations]
    ctx['symbol']               = [ entry['symbol']         for entry in calculations]
    ctx['strike']               = [ entry['strike']         for entry in calculations]
    ctx['exp_date']             = [ entry['exp_date']       for entry in calculations]
    ctx['max_profit']           = [ entry['max_profit']     for entry in calculations]
    ctx['call_price']           = [ entry['call_price']     for entry in calculations]
    ctx['curr_price']           = [ entry['curr_price']     for entry in calculations]
    ctx['max_profit_pc']        = [ entry['max_profit_pc']  for entry in calculations]
    ctx['effective_cost']       = [ entry['effective_cost'] for entry in calculations]
    return render(request, 'covered_calls.html', ctx)

def cash_secured_puts(request):
    ctx                               = {}
    tickers_str                       = ''
    calculations                      = []
    max_days_to_exp                   = 30
    max_otm_percent                   = 40
    max_itm_percent                   = 0
    min_premium_to_collatral_ratio    = 2

    if request.method == 'POST':
        max_days_to_exp                = int(request.POST.get('max_days_to_exp'))
        max_otm_percent                = float(request.POST.get('max_otm_percent'))
        max_itm_percent                = float(request.POST.get('max_itm_percent'))
        tickers_str                    = request.POST.get('tickers')
        tickers                        = re.split(',| ', tickers_str)
        if '' in tickers:
            tickers.remove('')
        min_premium_to_collatral_ratio = float(request.POST.get('min_premium_to_collatral_ratio'))
        calculations = StockUtils.CashSecuredPuts(tickers=tickers,
                                                  max_days_to_exp=max_days_to_exp,
                                                  max_otm_percent=max_otm_percent,
                                                  max_itm_percent=max_itm_percent,
                                                  min_premium_to_collatral_ratio=min_premium_to_collatral_ratio)
    ctx['tickers']                        = tickers_str
    ctx['max_days_to_exp']                = max_days_to_exp
    ctx['max_otm_percent']                = max_otm_percent
    ctx['max_itm_percent']                = max_itm_percent
    ctx['min_premium_to_collatral_ratio'] = min_premium_to_collatral_ratio
    ctx['iv']                             = [ entry['iv']                         for entry in calculations ]
    ctx['dte']                            = [ entry['dte']                        for entry in calculations ]
    ctx['delta']                          = [ entry['delta']                      for entry in calculations ]
    ctx['theta']                          = [ entry['theta']                      for entry in calculations ]
    ctx['symbol']                         = [ entry['symbol']                     for entry in calculations ]
    ctx['strike']                         = [ entry['strike']                     for entry in calculations ]
    ctx['premium']                        = [ entry['premium']                    for entry in calculations ]
    ctx['exp_date']                       = [ entry['exp_date']                   for entry in calculations ]
    ctx['curr_price']                     = [ entry['curr_price']                 for entry in calculations ]
    ctx['otm_percent']                    = [ entry['otm_percent']                for entry in calculations ]
    ctx['annual_return']                  = [ entry['annual_return']              for entry in calculations ]
    ctx['ownership_cost']                 = [ entry['ownership_cost']             for entry in calculations ]
    ctx['drop_to_loss_percent']           = [ entry['drop_to_loss_percent']       for entry in calculations ]
    ctx['premium_to_collatral_ratio']     = [ entry['premium_to_collatral_ratio'] for entry in calculations ]

    return render(request, 'cash_secured_puts.html', ctx)
