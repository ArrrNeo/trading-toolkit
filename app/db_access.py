#!/usr/bin/python3

# misc imports
from django.utils import timezone

# db imports
from app.models import stocks_held
from app.models import options_held
from app.models import portfolio_summary
from app.models import robinhood_stock_split_events
from app.models import robinhood_stock_order_history
from app.models import robinhood_traded_stocks
from app.models import robinhood_stock_order_history_next_urls

#refresh time in minutes
REFRESH_TIME = 1

class DbAccess():
    ############################################################################################################
    ## APIs to process data in database
    ############################################################################################################
    @staticmethod
    def calc_my_stock_positions():
        equity_total = 0
        today_unrealized_pl = 0
        total_unrealized_pl = 0

        summary = portfolio_summary.objects.all()
        if summary:
            summary = summary[0]
        else:
            summary = portfolio_summary()
            summary.timestamp = timezone.now()

        qset = stocks_held.objects.all()
        if not qset:
            return

        for item in qset:
            # if item.symbol present robinhood_stock_split_events, update average from first robinhood_traded_stocks
            if robinhood_stock_split_events.objects.filter(new_symbol=item.symbol):
                item.average_price = robinhood_traded_stocks.objects.filter(symbol=item.symbol)[0].pp_average_price
            item.pp_equity              = item.latest_price * item.quantity
            item.pp_cost_basis          = item.average_price * item.quantity
            item.pp_unrealized_pl       = item.pp_equity - item.pp_cost_basis
            item.pp_today_unrealized_pl = item.pp_equity - (item.open_price * item.quantity)
            item.save()

            equity_total             = equity_total + item.pp_equity
            total_unrealized_pl      = total_unrealized_pl + item.pp_unrealized_pl
            today_unrealized_pl      = today_unrealized_pl + item.pp_today_unrealized_pl

        summary.stocks_equity              = equity_total
        summary.today_stocks_unrealized_pl = today_unrealized_pl
        summary.total_stocks_unrealized_pl = total_unrealized_pl
        summary.save()

    @staticmethod
    def calc_my_option_positions():
        equity_total = 0
        today_unrealized_pl = 0
        total_unrealized_pl = 0

        summary = portfolio_summary.objects.all()
        if summary:
            summary = summary[0]
        else:
            summary = portfolio_summary()
            summary.timestamp = timezone.now()

        qset = options_held.objects.all()
        if not qset:
            return

        for item in qset:
            item.pp_equity               = item.current_price * item.quantity * item.trade_value_multiplier
            item.pp_cost_basis           = item.average_price * item.quantity * item.trade_value_multiplier
            item.pp_unrealized_pl        = item.pp_equity - item.pp_cost_basis
            item.pp_today_unrealized_pl  = item.pp_equity - (item.previous_close_price * item.quantity) * item.trade_value_multiplier
            item.save()

            equity_total               = equity_total + item.pp_equity
            total_unrealized_pl        = total_unrealized_pl + item.pp_unrealized_pl
            today_unrealized_pl        = today_unrealized_pl + item.pp_today_unrealized_pl

        summary.options_equity              = equity_total
        summary.today_options_unrealized_pl = today_unrealized_pl
        summary.total_options_unrealized_pl = total_unrealized_pl
        summary.save()

    @staticmethod
    def calc_portfolio_diversity(total_equity):
        qset = stocks_held.objects.all()
        if not qset:
            return

        for item in qset:
            item.pp_portfolio_diversity = (item.pp_equity / total_equity) * 100
            item.save()

        qset = options_held.objects.all()
        if not qset:
            return

        for item in qset:
            item.pp_portfolio_diversity = (item.pp_equity / total_equity) * 100
            item.save()

    @staticmethod
    def calc_pl_from_order_history():
        # in following dict, key is symbol and value is another dict with
        # quantity/avg_price/equity/realized_pl as keys of nested dict
        # init content of following dict from table robinhood_traded_stocks
        stocks = {}
        all_traded_stocks = robinhood_traded_stocks.objects.all()
        for obj in all_traded_stocks:
            # only read tickers which have been traded and processed. this check will protect against reading total_quantity as 0
            if obj.pp_last_trade_ts:
                symbol = obj.symbol
                stocks[symbol] = {}
                stocks[symbol]['cost_basis']        = obj.pp_cost_basis
                stocks[symbol]['average_price']     = obj.pp_average_price
                stocks[symbol]['total_quantity']    = obj.pp_total_quantity
                stocks[symbol]['total_realized_pl'] = obj.pp_total_realized_pl
                stocks[symbol]['today_realized_pl'] = obj.pp_today_realized_pl
                stocks[symbol]['last_trade_ts']     = obj.pp_last_trade_ts

        # for realized_pl today/total
        summary = portfolio_summary.objects.all()
        if summary:
            summary = summary[0]
        else:
            summary = portfolio_summary()
            summary.timestamp = timezone.now()

        orders = robinhood_stock_order_history.objects.filter(processed=False).order_by('timestamp')
        # parse complete robinhood_stock_order_history.
        # and calcaulate, avg, quantity, equity, realized_pl at end of each transaction
        for order in orders:
            sell_order_exception = False
            prev_ticker = ''
            # if symbol in stock_split:
            split_event = robinhood_stock_split_events.objects.filter(new_symbol=order.symbol)
            if split_event and split_event[0].processed == False:
                split_event = split_event[0]
                if order.timestamp.date() > split_event.date:
                    split_event.processed = True
                    split_event.save()
                    if split_event.ratio != 0:
                        # update previous stock avg and quantity
                        stocks[order.symbol]['total_quantity'] = stocks[order.symbol]['total_quantity'] * split_event.ratio
                        stocks[order.symbol]['average_price']  = stocks[order.symbol]['average_price'] / split_event.ratio
                    else:
                        sell_order_exception = True
                        prev_ticker = split_event.symbol
                        print ('adding exception for old_ticker: ' + split_event.symbol + ' new_ticker: ' + order.symbol)
            if order.order_type == 'buy':
                if order.symbol not in stocks:
                    stocks[order.symbol] = {}
                    stocks[order.symbol]['total_quantity']          = order.shares
                    stocks[order.symbol]['average_price']           = order.price
                    stocks[order.symbol]['cost_basis']              = order.shares * order.price
                    stocks[order.symbol]['order_realized_pl']       = 0
                    stocks[order.symbol]['total_realized_pl']       = 0
                    stocks[order.symbol]['today_realized_pl']       = 0
                else:
                    stocks[order.symbol]['total_quantity']          = stocks[order.symbol]['total_quantity'] + order.shares
                    stocks[order.symbol]['cost_basis']              = stocks[order.symbol]['cost_basis'] + order.shares * order.price
                    stocks[order.symbol]['average_price']           = stocks[order.symbol]['cost_basis'] / stocks[order.symbol]['total_quantity']
                    # no change in total_realized_pl/today_realized_pl, but realized_pl = 0 since this was buy order
                    stocks[order.symbol]['order_realized_pl']       = 0
            else:
                # order was sell
                if order.symbol not in stocks:
                    if sell_order_exception is True:
                        stocks[order.symbol] = {}
                        stocks[order.symbol]['cost_basis']        = 0
                        stocks[order.symbol]['total_quantity']    = 0
                        stocks[order.symbol]['today_realized_pl'] = 0
                        stocks[order.symbol]['total_realized_pl'] = 0
                        stocks[order.symbol]['average_price']     = stocks[prev_ticker]['cost_basis']/order.shares
                        stocks[order.symbol]['order_realized_pl'] = (order.price * order.shares) - stocks[prev_ticker]['cost_basis']
                        # delete prev ticker entry for dic
                        print ('deleting prev ticker: ' + prev_ticker)
                        stocks.pop(prev_ticker, None)
                    else:
                        # fatal error
                        print (order.symbol + ': sell without buy, check order history')
                        continue
                else:
                    stocks[order.symbol]['total_quantity'] = stocks[order.symbol]['total_quantity'] - order.shares
                    stocks[order.symbol]['cost_basis']     = stocks[order.symbol]['total_quantity'] * stocks[order.symbol]['average_price']
                    # realized_pl is only the profit/loss in this order
                    stocks[order.symbol]['order_realized_pl'] = (order.price - stocks[order.symbol]['average_price']) * order.shares


                stocks[order.symbol]['total_realized_pl']    = stocks[order.symbol]['total_realized_pl'] + stocks[order.symbol]['order_realized_pl']
                if order.timestamp.date() == timezone.now().date():
                    # order was sell and date was today
                    stocks[order.symbol]['today_realized_pl'] = stocks[order.symbol]['today_realized_pl'] + stocks[order.symbol]['order_realized_pl']

            stocks[order.symbol]['last_trade_ts'] = order.timestamp
            # update the same values in the transaction table
            order.processed           = True
            order.save()

            summary.total_realized_pl = summary.total_realized_pl + stocks[order.symbol]['order_realized_pl']
            summary.today_realized_pl = summary.today_realized_pl + stocks[order.symbol]['today_realized_pl']
            summary.save()

        # parse disctionary created
        # update same fields in robinhood_traded_stocks
        for symbol in stocks.keys():
            obj = robinhood_traded_stocks.objects.filter(symbol=symbol)
            if not obj:
                # fatal error
                print (symbol + ' not present in lookup table..')
            else:
                obj = obj[0]
                obj.pp_cost_basis        = stocks[symbol]['cost_basis']
                obj.pp_average_price     = stocks[symbol]['average_price']
                obj.pp_total_quantity    = stocks[symbol]['total_quantity']
                obj.pp_total_realized_pl = stocks[symbol]['total_realized_pl']
                obj.pp_today_realized_pl = stocks[symbol]['today_realized_pl']
                obj.pp_last_trade_ts     = stocks[symbol]['last_trade_ts']
                obj.save()

    ############################################################################################################
    ## APIs to get data from db
    ############################################################################################################
    @staticmethod
    def is_update_needed():
        summary = portfolio_summary.objects.all()
        if not summary:
            summary = portfolio_summary()
            summary.timestamp = timezone.now()
            summary.save()
            return True
        else:
            summary = summary[0]
            # if today date is > timestamp date, reset today_realized_pl
            if timezone.now().date() > summary.timestamp.date():
                summary.today_realized_pl = 0
                summary.today_unrealized_pl = 0

            refresh_time = summary.timestamp + timezone.timedelta(minutes=REFRESH_TIME)
            # check if update is needed
            if timezone.now() < refresh_time:
                return False
            # save the latest update timestamp
            summary.timestamp = timezone.now()
            summary.save()
            return True

    @staticmethod
    def get_from_db(x):
        obj = portfolio_summary.objects.all()
        if not obj:
            return 0
        if x == 'stocks_equity':
            return obj[0].stocks_equity
        if x == 'options_equity':
            return obj[0].options_equity
        if x == 'portfolio_cash':
            return obj[0].portfolio_cash
        if x == 'today_realized_pl':
            return obj[0].today_realized_pl
        if x == 'total_realized_pl':
            return obj[0].total_realized_pl
        if x == 'today_stocks_unrealized_pl':
            return obj[0].today_stocks_unrealized_pl
        if x == 'total_stocks_unrealized_pl':
            return obj[0].total_stocks_unrealized_pl
        if x == 'today_options_unrealized_pl':
            return obj[0].today_options_unrealized_pl
        if x == 'total_options_unrealized_pl':
            return obj[0].total_options_unrealized_pl
        if x == 'total_equity':
            return obj[0].total_equity

    @staticmethod
    def set_to_db(x, val):
        obj = portfolio_summary.objects.all()
        if not obj:
            return
        if x == 'stocks_equity':
            obj[0].stocks_equity = val
        if x == 'options_equity':
            obj[0].options_equity = val
        if x == 'portfolio_cash':
            obj[0].portfolio_cash = val
        if x == 'today_realized_pl':
            obj[0].today_realized_pl = val
        if x == 'total_realized_pl':
            obj[0].total_realized_pl = val
        if x == 'today_stocks_unrealized_pl':
            obj[0].today_stocks_unrealized_pl = val
        if x == 'total_stocks_unrealized_pl':
            obj[0].total_stocks_unrealized_pl = val
        if x == 'today_options_unrealized_pl':
            obj[0].today_options_unrealized_pl = val
        if x == 'total_options_unrealized_pl':
            obj[0].total_options_unrealized_pl = val
        if x == 'total_equity':
            obj[0].total_equity = val
        obj[0].save()
