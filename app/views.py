# -*- encoding: utf-8 -*-
"""
MIT License
Copyright (c) 2019 - present AppSeed.us
"""

import os
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

def covered_calls_chart(request):
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
        min_stock_price       = float(request.POST.get('min_stock_price'))
        max_stock_price       = float(request.POST.get('max_stock_price'))
        max_days_to_exp       = int(request.POST.get('max_days_to_exp'))
        min_max_profit_pc     = float(request.POST.get('min_max_profit_pc'))

        task = asyn_cc_chart.delay(min_stock_price=min_stock_price,
                                   max_stock_price=max_stock_price,
                                   min_itm_pc=min_itm_pc,
                                   max_itm_pc=max_itm_pc,
                                   min_max_profit_pc=min_max_profit_pc,
                                   max_days_to_exp=max_days_to_exp,
                                   debug_iterations=0)

        return render(request, 'covered_calls_chart_progress.html', { 'task_id' : task.task_id })
    else:
        ctx['min_itm_pc']           = min_itm_pc
        ctx['max_itm_pc']           = max_itm_pc
        ctx['min_stock_price']      = min_stock_price
        ctx['max_stock_price']      = max_stock_price
        ctx['max_days_to_exp']      = max_days_to_exp
        ctx['min_max_profit_pc']    = min_max_profit_pc
        return render(request, 'covered_calls_chart_results.html', ctx)

def covered_calls_chart_results(request):
    print (request)
    task_id = request.GET.get('task_id', None)
    if task_id is not None:
        task = AsyncResult(task_id)
        return render(request, 'covered_calls_chart_results.html', task.result)
        # return HttpResponse(json.dumps(task.result), content_type='application/json')
    else:
        return HttpResponse('No job id given.')
