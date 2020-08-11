# -*- encoding: utf-8 -*-
"""
MIT License
Copyright (c) 2019 - present AppSeed.us
"""

from django.db import models
from django.contrib.auth.models import User

class stocks_history(models.Model):
    date                        = models.DateField()                                                        # raw
    symbol                      = models.CharField(max_length=5)                                            # raw
    open_price                  = models.FloatField(default=0)                                              # raw
    high                        = models.FloatField(default=0)                                              # raw
    low                         = models.FloatField(default=0)                                              # raw
    close_price                 = models.FloatField(default=0)                                              # raw
    adj_price                   = models.FloatField(default=0)                                              # raw
    volume                      = models.IntegerField(default=0)                                            # raw

# Create your models here.
class portfolio_summary(models.Model):
    timestamp                    = models.DateTimeField()
    stocks_equity                = models.FloatField(default=0)                                             # processed
    options_equity               = models.FloatField(default=0)                                             # processed
    portfolio_cash               = models.FloatField(default=0)                                             # processed, sum of portfolio cash from all brokers
    today_stocks_realized_pl     = models.FloatField(default=0)                                             # processed
    total_stocks_realized_pl     = models.FloatField(default=0)                                             # processed
    today_stocks_unrealized_pl   = models.FloatField(default=0)                                             # processes
    total_stocks_unrealized_pl   = models.FloatField(default=0)                                             # processes
    today_options_unrealized_pl  = models.FloatField(default=0)                                             # processes
    total_options_unrealized_pl  = models.FloatField(default=0)                                             # processes
    total_equity                 = models.FloatField(default=0)                                             # processes

# table for stocks being held
class stocks_held(models.Model):
    # first set of fields are fetched from broker's API
    symbol                  = models.CharField(max_length=5)                                                # raw
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
    pp_long_term            = models.BooleanField(default=False)                                            # processed

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
    pp_long_term            = models.BooleanField(default=False)                                            # processed

class robinhood_traded_stocks(models.Model):
    symbol                 = models.CharField(max_length=5)                                                 # raw
    name                   = models.CharField(max_length=30)                                                # raw
    instrument_url         = models.CharField(max_length=92)                                                # raw
    # following fields are running numbers maintained while parsing order history
    pp_cost_basis          = models.FloatField(default=0)                                                   # processed
    pp_average_price       = models.FloatField(default=0)                                                   # processed
    pp_total_quantity      = models.FloatField(default=0)                                                   # processed
    pp_total_realized_pl   = models.FloatField(default=0)                                                   # processed
    pp_today_realized_pl   = models.FloatField(default=0)                                                   # processed
    pp_last_trade_ts       = models.DateTimeField(null=True)                                                # processed

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
    # following fields are calculated and added to table as order history is parsed                         #
    processed              = models.BooleanField(default=False)                                             # processed
    old_average_price      = models.FloatField(default=0)                                                   # processed
    new_average_price      = models.FloatField(default=0)                                                   # processed
    # avg from day prior to last day of order history will
    # be used to calculate today's realized/unrealized
