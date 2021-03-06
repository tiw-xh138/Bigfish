# -*- coding: utf-8 -*-
"""
Created on Wed Nov 25 20:41:04 2015

@author: BurdenBear
"""
from functools import partial

from Bigfish.core import DataGenerator, StrategyEngine, Strategy
from Bigfish.models.performance import StrategyPerformanceManagerOffline
from Bigfish.utils.quote import Bar
from Bigfish.utils.common import get_datetime
import Bigfish.data.forex_data as fx
import tushare as ts
import numpy as np
import pandas as pd


def _get_bar_from_dataframe(symbol, time_frame, data):
    bar = Bar(symbol)
    bar.time_frame = time_frame
    for field in ['open', 'high', 'low', 'close', 'volume']:
        setattr(bar, field, data[field])
    bar.time = get_datetime(data.name).timestamp()
    return bar


def _get_bar_from_dict(symbol, time_frame, data):
    bar = Bar(symbol)
    bar.time_frame = time_frame
    for field in ['open', 'high', 'low', 'close', 'volume']:
        setattr(bar, field, data[field])
    bar.time = data['ctime']
    return bar


class DataGeneratorTushare(DataGenerator):
    def _get_data(self, symbol, time_frame, start_time=None, end_time=None):
        if time_frame == 'D1':
            data = ts.get_hist_data(symbol, start_time, end_time)
            return data.apply(partial(_get_bar_from_dataframe, symbol, time_frame), axis=1).tolist()
        else:
            raise ValueError


class DataGeneratorMongoDB(DataGenerator):
    def _get_data(self, symbol, time_frame, start_time=None, end_time=None):
        data = fx.get_period_bars(symbol, time_frame, get_datetime(start_time).timestamp(),
                                  get_datetime(end_time).timestamp())
        return list(map(partial(_get_bar_from_dict, symbol, time_frame), data))


class Backtesting:
    def __init__(self, user, name, code, symbols=None, time_frame=None, start_time=None, end_time=None,
                 data_generator=DataGeneratorMongoDB):
        self.__setting = {'symbols': symbols, 'time_frame': time_frame, 'start_time': start_time, 'end_time': end_time}
        self.__strategy_engine = StrategyEngine(backtesting=True)
        self.__strategy = Strategy(self.__strategy_engine, user, name, code, symbols, time_frame, start_time, end_time)
        self.__strategy_parameters = None
        self.__strategy_engine.add_strategy(self.__strategy)
        self.__data_generator = data_generator(self.__strategy_engine)
        self.__performance_manager = None
        self.__performance = None

    def initialize(self):
        self.__strategy_engine.initialize()

    def start(self, paras=None, refresh=True):
        if paras is not None:
            self.__strategy.set_parameters(paras)
        self.initialize()
        self.__strategy_engine.start()
        self.__data_generator.start()
        self.__strategy_engine.wait()
        if refresh:
            self.__performance_manager = self.__get_performance_manager()

    def __get_performance_manager(self):
        # TODO ?????????????????????????????????
        if False:
            raise ValueError('please run the backtest first')
        return StrategyPerformanceManagerOffline(self.__data_generator.get_dataframe(),
                                                 self.__strategy_engine.get_deals(),
                                                 self.__strategy_engine.get_positions())

    def get_profit_records(self):
        return self.__strategy_engine.get_profit_records()

    def get_performance(self):
        return self.__performance_manager.get_performance()

    def get_output(self):
        return self.__strategy.get_output()

    def get_setting(self):
        return self.__setting

    @staticmethod
    def get_optimize_goals():
        return {'net_profit': '??????'}

    @staticmethod
    def get_optimize_types():
        return {'enumerate': '??????', 'genetic': '??????'}

    def get_parameters(self):
        if self.__strategy_parameters is None:
            temp = self.__strategy.get_parameters()
            for handle_name in temp.keys():
                for para_name, values in temp[handle_name].items():
                    temp[handle_name][para_name] = {'default': values, 'type': str(type(values))}
            self.__strategy_parameters = temp
        return self.__strategy_parameters

    def _enumerate_optimize(self, ranges, goal, num):
        stack = []
        range_length = []
        parameters = {}
        result = []
        head_index = []

        def get_range(range_info):
            return np.arange(range_info['start'], range_info['end'] + range_info['step'], range_info['step'])

        for handle, paras in ranges.items():
            parameters[handle] = {}
            for para, value in paras.items():
                range_value = get_range(value)
                stack.append({'handle': handle, 'para': para, 'range': range_value})
                head_index.append('%s(%s)' % (para, handle))
                range_length.append(len(range_value))
        n = len(stack)
        index = [-1] * n
        head = [0] * n

        def set_paras(n, handle=None, para=None, range=None):
            nonlocal parameters, head, index
            parameters[handle][para] = head[n] = range[index[n]]

        i = 0
        finished = False
        while 1:
            index[i] += 1
            while index[i] >= range_length[i]:
                if i == 0:
                    finished = True
                    break
                index[i] = -1
                i -= 1
                index[i] += 1
            if finished:
                break
            set_paras(i, **stack[i])
            if i == n - 1:
                self.start(parameters, refresh=False)
                head = pd.Series(head, index=head_index)
                performance_manager = self.__get_performance_manager()
                optimize_info = performance_manager.get_performance().optimize_info.copy()
                target = optimize_info[goal]
                del optimize_info[goal]
                result.append(pd.concat([head, pd.Series([target], index=[goal]), optimize_info]))
            else:
                i += 1
        result = pd.DataFrame(result).sort_values(goal, ascending=False)
        result.index.name = '_'
        return result.iloc[:num]

    def _genetic_optimize(self, ranges, goal):
        pass

    def optimize(self, ranges, type, goal, num=50):
        if not ranges:
            return
        if type is None:
            type = "enumerate"
        # TODO ?????????????????????
        if goal is None:
            goal = "??????($)"
        goal = "??????($)"
        optimizer = getattr(self, '_%s_optimize' % type)
        return optimizer(ranges, goal, num)


if __name__ == '__main__':
    from Bigfish.models.model import User
    from Bigfish.store.directory import UserDirectory
    from Bigfish.utils.ligerUI_util import DataframeTranslator
    import time

    start_time = time.time()
    with open('../test/testcode3.py') as f:
        code = f.read()
    user = User('10032')
    backtest = Backtesting(user, 'test', code, ['EURUSD'], 'M30', '2015-01-01', '2016-01-01',
                           data_generator=DataGeneratorMongoDB)
    backtest.start()
    translator = DataframeTranslator()
    user_dir = UserDirectory(user)
    print(user_dir.get_sys_func_list())
    print(backtest.get_profit_records())  # ????????????????????????
    print(backtest.get_parameters())  # ??????????????????????????????????????????
    performance = backtest.get_performance()  # ???????????????????????????
    print('trade_info:\n%s' % performance._manager.trade_info)
    print('trade_summary:\n%s' % performance.trade_summary)
    print('trade_details:\n%s' % performance.trade_details)
    print(translator.dumps(performance.trade_details))
    print('strategy_summary:\n%s' % performance.strategy_summary)
    print('optimize_info:\n%s' % performance.optimize_info)
    print('info_on_home_page\n%s' % performance.get_info_on_home_page())
    print(performance.get_factor_list())
    print(performance.yield_curve)
    print('ar:\n%s' % performance.ar)  # ???????????????
    print('risk_free_rate:\n%s' % performance._manager.risk_free_rate)  # ??????????????????
    print('volatility:\n%s' % performance.volatility)  # ?????????
    print('sharpe_ratio:\n%s' % performance.sharpe_ratio)  # sharpe??????
    print('max_drawdown:\n%s' % performance.max_drawdown)  # ????????????
    print('output:\n%s' % backtest.get_output())
    print(time.time() - start_time)
    paras = {
        'handle': {'slowlength': {'start': 18, 'end': 20, 'step': 1},
                   'fastlength': {'start': 10, 'end': 10, 'step': 1},
                   'lots': {'start': 100, 'end': 100, 'step': 1}}}
    optimize = backtest.optimize(paras, None, None)
    print('optimize\n%s' % optimize)
    print(time.time() - start_time)
