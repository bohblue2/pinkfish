"""
stategy
---------
"""

# use future imports for python 3.x forward compatibility
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import

# other imports
import pandas as pd
import matplotlib.pyplot as plt
import datetime
from talib.abstract import *

# project imports
import pinkfish as pf

pf.DEBUG = False

class Strategy():

    def __init__(self, symbol, capital, start, end, use_adj=False,
                 period=7, max_positions=4):
        self._symbol = symbol
        self._capital = capital
        self._start = start
        self._end = end
        self._use_adj = use_adj
        self._period = period
        self._max_positions = max_positions
        self._positions = 0
        
    def _algo(self):
        """ Algo:
            1. The SPY is above its 200-day moving average
            2. The SPY closes at a X-day low, buy with full capital.
            3. If the SPY closes at a X-day high, sell some.
               If it sets further highs, sell some more, etc...
            4. If you have free cash, use it all when fresh lows are set.
        """
        self._tlog.cash = self._capital
        stop_loss = 0

        for i, row in enumerate(self._ts.itertuples()):

            date = row.Index.to_pydatetime()
            high = row.high
            low = row.low
            close = row.close
            sma200 = row.sma200
            period_high = row.period_high
            period_low = row.period_low
            end_flag = True if (i == len(self._ts) - 1) else False
            shares = 0

            # buy
            if (close > sma200
                and close == period_low
                and not end_flag):
                
                # calc number of shares
                shares = self._tlog.calc_shares(price=close, cash=self._tlog.cash)
                
                # if we have enough cash to buy any shares, then buy them
                if shares > 0:

                    # enter buy in trade log
                    self._tlog.enter_trade(date, close, shares)                
                    # set stop loss
                    stop_loss = 0*close
                    # set positions to max_positions
                    self._positions = self._max_positions

            # sell
            elif (self._tlog.num_open_trades() > 0
                  and (close == period_high
                       or low < stop_loss
                       or end_flag)):
                
                if end_flag:
                    shares = self._tlog.shares
                else:
                    shares = int(self._tlog.shares / (self._positions))
                    self._positions -= 1

                # enter sell in trade log
                shares = self._tlog.exit_trade(date, close, shares)

            if shares > 0:
                pf.DBG("{0} BUY  {1} {2} @ {3:.2f}".format(
                       date, shares, self._symbol, close))
            elif shares < 0:
                pf.DBG("{0} SELL {1} {2} @ {3:.2f}".format(
                       date, -shares, self._symbol, close))

            # record daily balance
            self._dbal.append(date, high, low, close,
                              self._tlog.shares, self._tlog.cash)

    def run(self):
        self._ts = pf.fetch_timeseries(self._symbol)
        self._ts = pf.select_tradeperiod(self._ts, self._start,
                                         self._end, use_adj=False)

        # Add technical indicator: 200 day sma
        sma200 = SMA(self._ts, timeperiod=200)
        self._ts['sma200'] = sma200

        # Add technical indicator: X day high, and X day low
        period_high = pd.Series(self._ts.close).rolling(self._period).max()
        period_low = pd.Series(self._ts.close).rolling(self._period).min()
        self._ts['period_high'] = period_high
        self._ts['period_low'] = period_low
        
        self._ts, self._start = pf.finalize_timeseries(self._ts, self._start)
        
        self._tlog = pf.TradeLog()
        self._dbal = pf.DailyBal()

        self._algo()

    def get_logs(self):
        """ return DataFrames """
        self.tlog = self._tlog.get_log()
        self.dbal = self._dbal.get_log(self.tlog)
        return self.tlog, self.dbal

    def get_stats(self):
        stats = pf.stats(self._ts, self.tlog, self.dbal, self._capital)
        return stats

def summary(strategies, *metrics):
    """ Stores stats summary in a DataFrame.
        stats() must be called before calling this function """
    index = []
    columns = strategies.index
    data = []
    # add metrics
    for metric in metrics:
        index.append(metric)
        data.append([strategy.stats[metric] for strategy in strategies])

    df = pd.DataFrame(data, columns=columns, index=index)
    return df

def plot_bar_graph(df, metric):
    """ Plot Bar Graph: Strategy
        stats() must be called before calling this function """
    df = df.loc[[metric]]
    df = df.transpose()
    fig = plt.figure()
    axes = fig.add_subplot(111, ylabel=metric)
    df.plot(kind='bar', ax=axes, legend=False)
    axes.set_xticklabels(df.index, rotation=0)
