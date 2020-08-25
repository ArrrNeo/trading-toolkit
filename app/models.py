# -*- encoding: utf-8 -*-
"""
MIT License
Copyright (c) 2019 - present AppSeed.us
"""

from django.db import models
from django.contrib.auth.models import User

class stock_daily_db_table(models.Model):
    date                         = models.DateField(unique=True)
    day_pl                       = models.FloatField()
    equity_at_close              = models.FloatField()
    day_realized_pl              = models.FloatField()
    portfolio_end                = models.CharField(max_length=1000)

# Create your models here.
class portfolio_summary(models.Model):
    timestamp                    = models.DateTimeField()
    silver_gold_equity           = models.FloatField(default=0)                                             # processed
    stocks_equity                = models.FloatField(default=0)                                             # processed
    options_equity               = models.FloatField(default=0)                                             # processed
    portfolio_cash               = models.FloatField(default=0)                                             # processed, sum of portfolio cash from all brokers
    total_stocks_unrealized_pl   = models.FloatField(default=0)                                             # processes
    total_options_unrealized_pl  = models.FloatField(default=0)                                             # processes
    total_equity                 = models.FloatField(default=0)                                             # processes

# table for stocks being held
class stocks_held(models.Model):
    # first set of fields are fetched from broker's API
    symbol                  = models.CharField(max_length=5)                                                # raw
    keywords                = models.CharField(max_length=100)                                              # raw
    average_price           = models.FloatField()                                                           # raw
    quantity                = models.FloatField()                                                           # raw
    open_price              = models.FloatField()                                                           # raw
    prev_close_price        = models.FloatField()                                                           # raw
    latest_price            = models.FloatField()                                                           # raw
    # following fields are post processed after broker's API fetching is complete
    pp_equity               = models.FloatField(default=0)                                                  # processed
    pp_cost_basis           = models.FloatField(default=0)                                                  # processed
    pp_unrealized_pl        = models.FloatField(default=0)                                                  # processed
    pp_today_unrealized_pl  = models.FloatField(default=0)                                                  # processed
    pp_portfolio_diversity  = models.FloatField(default=0)                                                  # processed

# table for options being held
class options_held(models.Model):
    # first set of fields are fetched from broker's API
    symbol                  = models.CharField(max_length=5)                                                # raw
    option_type             = models.CharField(max_length=5)                                                # raw
    expiration_date         = models.CharField(max_length=20)                                               # raw
    # option_id: is robinhood specific field
    option_id               = models.CharField(max_length=52)                                               # raw
    strike_price            = models.FloatField()                                                           # raw
    average_price           = models.FloatField()                                                           # raw
    quantity                = models.FloatField()                                                           # raw
    previous_close_price    = models.FloatField()                                                           # raw
    current_price           = models.FloatField()                                                           # raw
    trade_value_multiplier  = models.FloatField()                                                           # raw
    # following fields are post processed after broker's API fetching is complete
    pp_equity               = models.FloatField(default=0)                                                  # processed
    pp_cost_basis           = models.FloatField(default=0)                                                  # processed
    pp_unrealized_pl        = models.FloatField(default=0)                                                  # processed
    pp_today_unrealized_pl  = models.FloatField(default=0)                                                  # processed
    pp_portfolio_diversity  = models.FloatField(default=0)                                                  # processed

class robinhood_traded_stocks(models.Model):
    symbol                 = models.CharField(max_length=5)                                                 # raw
    name                   = models.CharField(max_length=30)                                                # raw
    instrument_url         = models.CharField(max_length=92)                                                # raw
    pp_average_price       = models.FloatField(default=0)                                                   # processed
    pp_realized_pl         = models.FloatField(default=0)                                                   # processed

class robinhood_stock_split_events(models.Model):
    symbol                 = models.CharField(max_length=5)                                                 # raw
    new_symbol             = models.CharField(max_length=5)                                                 # raw
    date                   = models.DateField()                                                             # raw
    # ratio is new to old ratio, for example if stock splits into 2,                                        #
    # then ratio would be 2, and if stock reverse-splits from 2 to 1,                                       #
    # then ratio would be 0.5                                                                               #
    ratio                  = models.FloatField()                                                            # raw
    processed              = models.BooleanField(default=False)                                             # processed

# stores order history next URLs good for fetching only latest orders
class robinhood_stock_order_history_next_urls(models.Model):
    next_url               = models.CharField(max_length=100)                                               # raw

class robinhood_stock_order_history(models.Model):
    symbol                 = models.CharField(max_length=5)                                                 # raw
    order_type             = models.CharField(max_length=5, default = 'buy')                                # raw
    shares                 = models.FloatField()                                                            # raw
    price                  = models.FloatField()                                                            # raw
    timestamp              = models.DateTimeField()                                                         # raw
    processed              = models.BooleanField(default=False)                                             # processed
