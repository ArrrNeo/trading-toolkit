#!/usr/bin/python3

# misc imports
# import pprint
import datetime
from django.utils import timezone
from app.stock_utils import StockUtils

# db imports
from app.models import stocks_held
from app.models import options_held
from app.models import portfolio_summary
from app.models import stock_daily_db_table
from app.models import robinhood_traded_stocks
from app.models import robinhood_stock_split_events
from app.models import robinhood_stock_order_history
from app.models import robinhood_stock_order_history_next_urls

#refresh time in minutes
REFRESH_TIME = 15

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
            item.pp_today_unrealized_pl = item.pp_equity - (item.prev_close_price * item.quantity)
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
    def process_all_orders():
        portfolio = {}
        stock_daily_table = []
        total_stocks_realized_pl = 0
        delta = datetime.timedelta(days=1)

        orders = robinhood_stock_order_history.objects.all().order_by('timestamp')
        order_list = list(orders.values())
        curr_date = order_list[0]['timestamp'].date()
        end_date = order_list[-1]['timestamp'].date()
        idx = 0
        all_tickers = list(set([x['symbol'] for x in order_list]))
        history_data = StockUtils.getHistoryData(all_tickers, curr_date, end_date)
        while curr_date <= end_date:
            if StockUtils.is_market_holiday(curr_date, history_data):
                curr_date += delta
                continue
            idx = DbAccess.process_day_orders(idx, curr_date, portfolio, order_list, stock_daily_table, history_data)
            total_stocks_realized_pl = total_stocks_realized_pl + stock_daily_table[-1]['day_realized_pl']
            curr_date += delta

        DbAccess.set_to_db('total_stocks_realized_pl', total_stocks_realized_pl)
        DbAccess.set_to_db('today_stocks_realized_pl', stock_daily_table[-1]['day_realized_pl'])

        for key in portfolio.keys():
            obj = robinhood_traded_stocks.objects.filter(symbol=key)[0]
            obj.pp_average_price = portfolio[key]['average_price']
            obj.save()

        django_list = [stock_daily_db_table(**vals) for vals in stock_daily_table]
        stock_daily_db_table.objects.bulk_create(django_list)

        # todo: make sure final portfolio matches rh_fetched_portfolio.

    @staticmethod
    def process_day_orders(idx, curr_date, portfolio, order_list, stock_daily_table, history_data):
        day_entry = {}
        day_change = 0
        day_realized_pl = 0

        try:
            equity_at_prev_close = stock_daily_table[-1][equity_at_close]
        except Exception as e:
            equity_at_prev_close = 0
        day_entry['date'] = curr_date
        # following will be used later when calculating stocks traded in given period
        # day_entry['portfolio_start'] = portfolio
        while idx < len(order_list):
            if order_list[idx]['timestamp'].date() == curr_date:
                order_change, order_realized_pl = DbAccess.process_single_order(portfolio, order_list[idx])
                day_change = day_change + order_change
                day_realized_pl = day_realized_pl + order_realized_pl
            else:
                break
            idx = idx + 1

        # calcaulate equity_at_close
        equity_at_close = StockUtils.getHistoricValue(portfolio, curr_date, history_data)
        day_pl = equity_at_close - equity_at_prev_close + day_change
        day_entry['equity_at_close'] = equity_at_close
        # following will be used later when calculating stocks traded in given period
        # day_entry['portfolio_end']   = portfolio
        day_entry['day_pl']          = day_pl
        day_entry['day_realized_pl'] = day_realized_pl
        stock_daily_table.append(day_entry)
        # delete enrties with 0 shares
        zero_stocks = [x for x in portfolio.keys() if portfolio[x]['total_quantity'] == 0]
        for ticker in zero_stocks:
            portfolio.pop(ticker, 'None')
        return idx

    @staticmethod
    def process_single_order(portfolio, order):
        DbAccess.update_stock_for_split(portfolio, order)
        if order['order_type'] == 'buy':
            return DbAccess.process_buy_order(portfolio, order)
        else:
            return DbAccess.process_sell_order(portfolio, order)

    @staticmethod
    def update_stock_for_split(portfolio, order):
        split_event = robinhood_stock_split_events.objects.filter(new_symbol=order['symbol'])

        if not split_event:
            return

        if split_event[0].processed == True:
            return

        split_event = split_event[0]
        if order['timestamp'].date() < split_event.date:
            return

        print ('processing split old: ' + split_event.symbol + ' new: ' + split_event.new_symbol)

        split_event.processed = True
        split_event.save()
        if split_event.new_symbol != split_event.symbol:
            # delete previous entry and, add new entry with same amount of equity
            cost_basis = portfolio[split_event.symbol]['cost_basis']
            portfolio[split_event.symbol] = {}
            portfolio[split_event.symbol]['cost_basis'] = 0
            portfolio[split_event.symbol]['average_price'] = 0
            portfolio[split_event.symbol]['total_quantity'] = 0
            portfolio[split_event.new_symbol] = {}
            portfolio[split_event.new_symbol]['cost_basis'] = cost_basis
            portfolio[split_event.new_symbol]['total_quantity'] = 0
        if split_event.ratio != 0:
            # update previous stock avg and quantity
            portfolio[order['symbol']]['total_quantity'] = portfolio[order['symbol']]['total_quantity'] * split_event.ratio
            portfolio[order['symbol']]['average_price']  = portfolio[order['symbol']]['average_price'] / split_event.ratio

    @staticmethod
    def process_buy_order(portfolio, order):
        # for net sales change is +ve, for net purchases change is -ve
        # order was buy
        if order['symbol'] not in portfolio:
            portfolio[order['symbol']] = {}
            portfolio[order['symbol']]['total_quantity'] = order['shares']
            portfolio[order['symbol']]['average_price']  = order['price']
            portfolio[order['symbol']]['cost_basis']     = order['shares'] * order['price']
        else:
            portfolio[order['symbol']]['total_quantity'] = portfolio[order['symbol']]['total_quantity'] + order['shares']
            portfolio[order['symbol']]['cost_basis']     = portfolio[order['symbol']]['cost_basis'] + order['shares'] * order['price']
            portfolio[order['symbol']]['average_price']  = portfolio[order['symbol']]['cost_basis'] / portfolio[order['symbol']]['total_quantity']
        change = -1 * (order['shares'] * order['price'])
        return change, 0

    @staticmethod
    def process_sell_order(portfolio, order):
        # for net sales change is +ve, for net purchases change is -ve
        # order was sell
        change = order['shares'] * order['price']
        if order['symbol'] not in portfolio:
            print (order['symbol'] + ': sell without buy, check order history. fix for BEPC.')
            realized_profit_loss = change
        else:
            if portfolio[order['symbol']]['total_quantity'] == 0:
                # this was result of split
                realized_profit_loss = change - portfolio[order['symbol']]['cost_basis']
            else:
                portfolio[order['symbol']]['total_quantity'] = portfolio[order['symbol']]['total_quantity'] - order['shares']
                portfolio[order['symbol']]['cost_basis'] = portfolio[order['symbol']]['total_quantity'] * portfolio[order['symbol']]['average_price']
                realized_profit_loss = order['shares'] * (order['price'] - portfolio[order['symbol']]['average_price'])
        obj = robinhood_traded_stocks.objects.filter(symbol=order['symbol'])[0]
        obj.pp_realized_pl = obj.pp_realized_pl + realized_profit_loss
        obj.save()
        return change, realized_profit_loss

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
        if x == 'today_stocks_realized_pl':
            return obj[0].today_stocks_realized_pl
        if x == 'total_stocks_realized_pl':
            return obj[0].total_stocks_realized_pl
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
        if x == 'today_stocks_realized_pl':
            obj[0].today_stocks_realized_pl = val
        if x == 'total_stocks_realized_pl':
            obj[0].total_stocks_realized_pl = val
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
