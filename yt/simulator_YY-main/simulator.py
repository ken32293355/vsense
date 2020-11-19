import struct
import time
import numpy as np
import pandas as pd
import datetime as dt
# from snds import snds
# from sibs import sibs
# from sots import sots
from yy24 import YY24
from yy25 import YY25
from yy26 import YY26
from tqdm import tqdm



import os

class simulator:

    def __init__(self, strategy, data_path, delay_ms):
        self.strategy = strategy
        print('SIM REG LOB', self.strategy.lob_slist)
        print('SIM REG TICK', self.strategy.tick_slist)
        self.order = pd.DataFrame(columns=['order_id', 'action', 'order_option', 'side', 'sid', 'price', 'vol', 
                                           'msg_id', 'b4v', 'fillv', 'unfillv', 'cancel', 'replace'])
        self.ordern = 0
        self.dtime = 0 # 當前的時間(資料時間)
        self.delay = delay_ms
        self.reportlist = [[999999999, 0]]
        self.load_data(data_path)
        self.lob = pd.DataFrame(columns=self.data.columns)


    def load_data(self, data_path):
        self.data = pd.read_csv(data_path, dtype={'sid':str, 'txtime':int, 'seq':int, 'volume':int, 'codec':int})
        self.data = self.data.loc[self.data['sid'].isin(self.strategy.lob_slist) | \
                                  ((self.data['tick']>0) & self.data['sid'].isin(self.strategy.tick_slist)),]
        self.data = self.data.reset_index(drop=True)
        print(f'SIM TOTAL DATA LENGTH {len(self.data)}')


    def send_tick(self, datai):
        sid = str.encode(self.data.loc[datai, 'sid'])
        payload = [self.data.loc[datai, 'txtime'], self.data.loc[datai, 'seq'], 0, sid, 
                   self.data.loc[datai, 'tick'], self.data.loc[datai, 'volume'], 
                   self.data.loc[datai, 'txtime'], 0, 0, 0, self.data.loc[datai, 'codec']]
        tick_t = struct.pack('IIQ24sddIIIII', *payload)
        self.strategy.onTickEvent(tick_t)


    def update_lob(self, datai):
        t_i = self.lob.index[self.lob['sid']==self.data.loc[datai, 'sid']].tolist()
        if len(t_i)>0 :
            self.lob.loc[t_i] = self.data.loc[datai].tolist()
        else :
            self.lob.loc[len(self.lob)] = self.data.loc[datai].tolist()


    def send_lob(self, datai):
        sid = str.encode(self.data.loc[datai, 'sid'])
        # txtime, seq, prod_code, sid, num_bid, num_ask,
        # bid1, bidv1, bid2, bidv2, bid3, bidv3, bid4, bidv4, bid5, bidv5,
        # ask1, askv1, ask2, askv2, ask3, askv3, ask4, askv4, ask5, askv5
        payload = [self.data.loc[datai, 'txtime'], self.data.loc[datai, 'seq'], 0, sid, 0, 0] + \
                   self.data.iloc[datai, 3:23].tolist()
        lob_t = struct.pack('IIQ24sIIdddddddddddddddddddd', *payload)
        self.strategy.onLobEvent(lob_t)


    def check_order(self) :
        
        stolen = len(self.strategy.order_list)

        while self.ordern < stolen:

            order_type, order_len, sid, strategy_name, order_id,\
            side, vol, price, market, msg_id, action,\
            order_mode, order_option, unuse \
            = struct.unpack('II20s20s24sIIdIiIIII', self.strategy.order_list[self.ordern])

            sid = sid.decode('utf-8').replace('\x00', '').replace(' ', '')
            order_id = order_id.decode('utf-8').replace('\x00', '').replace(' ', '')
            t_on = len(self.order)

            if action == 1 : # new order
                if order_option == 7 : # market order
                    if side == 1 :
                        price = 99999
                    elif side == 2 :
                        price = 0.001
                order_id = "A{:0>4d}".format(t_on)
                fillv = 0
                unfillv = vol
                cancel = 0
                replace = 0
                b4v = self.get_before_vol(sid, side, price)
                # print("**** order: ", t_on, "b4v: ", b4v)
                self.order.loc[t_on] = [order_id, action, order_option, side, sid, price, vol, msg_id, 
                                        b4v, fillv, unfillv, cancel, replace]
                report_status = 1 # new confirm
                self.append_report(sid, order_id, side, vol, price, msg_id, report_status, 0)
                
                # 檢查是否直接 hit bid ask
                lobi = self.lob.index[self.lob['sid']==sid].tolist()
                if len(lobi)>0 :
                    lobi = lobi[0]
                    self.hit_bid_ask(t_on, self.lob.loc[lobi])

            elif action == 3 : # reduce quantity
                t_i = self.order.index[self.order['order_id']==order_id].tolist()
                if len(t_i)>0 :
                    t_i = t_i[0]
                    if self.order.loc[t_i, 'unfillv'] > 0 and vol > self.order.loc[t_i, 'fillv'] : 
                        # 尚未完全成交 and 修改後的量需大於已經成交量
                        self.order.loc[t_i, 'vol'] = vol
                        self.order.loc[t_i, 'unfillv'] = vol - self.order.loc[t_i, 'fillv']
                        self.order.loc[t_i, 'replace'] = self.order.loc[t_i, 'replace'] + 1
                        self.append_report(sid, order_id, side, 0, 0, msg_id, 3, 0) # replace confirm
                    else : # already fill, cancel reject
                        self.append_report(sid, order_id, side, 0, 0, msg_id, 8, 0) # replace reject
                else : # cant find order_id, cancel reject
                    self.append_report(sid, order_id, side, 0, 0, msg_id, 8, 0) # replace reject

            elif action == 4 : # order cancel
                t_i = self.order.index[self.order['order_id']==order_id].tolist()
                if len(t_i)>0 :
                    t_i = t_i[0]
                    if self.order.loc[t_i, 'unfillv'] > 0 :
                        # print("**** cancel order: ", t_i, "b4v: ", self.order.loc[t_i, 'b4v'])
                        self.order.loc[t_i, 'unfillv'] = 0
                        self.order.loc[t_i, 'cancel'] = self.order.loc[t_i, 'cancel'] + 1
                        self.append_report(sid, order_id, side, 0, 0, msg_id, 2, 0) # cancel confirm
                        
                    else : # already fill, cancel reject
                        self.append_report(sid, order_id, side, 0, 0, msg_id, 6, 0) # cancel reject
                else : # cant find order_id, cancel reject
                    self.append_report(sid, order_id, side, 0, 0, msg_id, 6, 0) # cancel reject

            self.ordern = self.ordern + 1


    def get_before_vol(self, sid, side, price):
        lobi = self.lob.index[self.lob['sid']==sid].tolist()
        if len(lobi) <= 0 :
            b4v = 0
        else :
            lobi = lobi[0]
            if side == 1 : # BUY
                t_bid = np.array(self.lob.loc[lobi, [f'bid{x}' for x in range(1,6)]])
                t_bidv = np.array(self.lob.loc[lobi, [f'bidv{x}' for x in range(1,6)]])
                b4v = sum(t_bidv[t_bid>=price]) # >=price的bid共有幾張
            if side == 2 : # ASK
                t_ask = np.array(self.lob.loc[lobi, [f'ask{x}' for x in range(1,6)]])
                t_askv = np.array(self.lob.loc[lobi, [f'askv{x}' for x in range(1,6)]])
                b4v = sum(t_askv[t_ask<=price]) # <=price的ask共有幾張
        return(b4v)


    def report_fill(self, orderi, fillv, fillp):
        if self.order.loc[orderi, 'unfillv'] > 0 : # PARTIAL FILL
            report_status = 5
        else : # FILL
            report_status = 4
        self.append_report(self.order.loc[orderi, 'sid'], self.order.loc[orderi, 'order_id'], 
                         self.order.loc[orderi, 'side'], self.order.loc[orderi, 'vol'], fillp,
                         self.order.loc[orderi, 'msg_id'], report_status, fillv)            


    def hit_bid_ask(self, orderi, lob):
        # lob原先無codec，這裡的codec是在整理raw data時進行處理
        if lob['codec']==16 : # 只有盤中能去hit bid ask
            side = self.order.loc[orderi, 'side']
            price = self.order.loc[orderi, 'price']
            if side==1 and price>=lob['ask1'] : # side 1 = BUY
                for ri in range(1, 6):
                    task = lob[f'ask{ri}']
                    taskv = lob[f'askv{ri}']
                    if price>=task and self.order.loc[orderi, 'unfillv']>0 :
                        fillv = min(taskv, self.order.loc[orderi, 'unfillv'])
                        self.order.loc[orderi, 'fillv'] = self.order.loc[orderi, 'fillv'] + fillv
                        self.order.loc[orderi, 'unfillv'] = self.order.loc[orderi, 'vol'] - self.order.loc[orderi, 'fillv']
                        self.report_fill(orderi, fillv, task)
            elif side==2 and price<=lob['bid1'] : # side 2 = SELL
                for ri in range(1, 6):
                    tbid = lob[f'bid{ri}']
                    tbidv = lob[f'bidv{ri}']
                    if price<=tbid and self.order.loc[orderi, 'unfillv']>0 :
                        fillv = min(tbidv, self.order.loc[orderi, 'unfillv'])
                        self.order.loc[orderi, 'fillv'] = self.order.loc[orderi, 'fillv'] + fillv
                        self.order.loc[orderi, 'unfillv'] = self.order.loc[orderi, 'vol'] - self.order.loc[orderi, 'fillv']
                        self.report_fill(orderi, fillv, tbid)


    def check_order_fill_by_lob(self, datai) :
        # LOB 移動到 掛單的位置 因此有成交
        # 短時間內相似 LOB 會一直不斷出現 算量沒有意義
        # 故當 LOB 移動到掛單位置則 "全部成交"且成交於"掛單價"
        codec = self.data.loc[datai, 'codec'] 
        if codec == 16 : # 一定要盤中
            sid = self.data.loc[datai, 'sid']
            bid1 = self.data.loc[datai, 'bid1']
            ask1 = self.data.loc[datai, 'ask1']
            for orderi in range(len(self.order)) :
                if self.order.loc[orderi, 'sid']==sid and self.order.loc[orderi, 'unfillv'] > 0 :
                    o_price = self.order.loc[orderi, 'price'] # 掛單價格
                    if (self.order.loc[orderi, 'side']==1 and o_price>=ask1) or \
                       (self.order.loc[orderi, 'side']==2 and o_price<=bid1) :
                        t_fillv = self.order.loc[orderi, 'unfillv']
                        self.order.loc[orderi, 'fillv'] = self.order.loc[orderi, 'fillv'] + self.order.loc[orderi, 'unfillv']
                        self.order.loc[orderi, 'unfillv'] = 0
                        self.report_fill(orderi, t_fillv, o_price) # LOB 向下撞到買單/向上撞到賣單，故成交價格為掛單價


    def check_order_fill_by_tick(self, datai) :
        codec = self.data.loc[datai, 'codec'] 
        if codec!=128 : # 非試搓
            sid = self.data.loc[datai, 'sid']
            tick = self.data.loc[datai, 'tick']
            vol = self.data.loc[datai, 'volume']
            for orderi in range(len(self.order)) :
                if self.order.loc[orderi, 'sid']==sid and self.order.loc[orderi, 'unfillv'] > 0 :
                    if (self.order.loc[orderi, 'side']==1 and self.order.loc[orderi, 'price']>=tick) or \
                       (self.order.loc[orderi, 'side']==2 and self.order.loc[orderi, 'price']<=tick):
                        if vol <= self.order.loc[orderi, 'b4v'] :
                            self.order.loc[orderi, 'b4v'] = self.order.loc[orderi, 'b4v'] - vol
                        else :
                            t_fillv = min(vol-self.order.loc[orderi, 'b4v'], self.order.loc[orderi, 'unfillv'])
                            self.order.loc[orderi, 'b4v'] = 0
                            self.order.loc[orderi, 'fillv'] = self.order.loc[orderi, 'fillv'] + t_fillv
                            self.order.loc[orderi, 'unfillv'] = self.order.loc[orderi, 'vol'] - self.order.loc[orderi, 'fillv']
                            if codec==8 or codec==4 : # 為開盤(8)或者收盤(4)
                                t_fillp = tick # 開收盤之tick會成交在開收盤價
                            else :
                                t_fillp = self.order.loc[orderi, 'price'] # 掛單價格
                            self.report_fill(orderi, t_fillv, t_fillp)


    def append_report(self, sid, order_id, side, vol, price, msg_id,
                      report_status, filled_quantity):

        st_name = str.encode('simulator')
        sid = str.encode(sid)
        order_id = str.encode(order_id)
        market = 2 # 1 = taifex, 2 = twse
        report_t = struct.pack('20s20s24sIIdIiII',
                               sid, st_name, order_id, side, vol, price, 
                               market, msg_id, report_status, filled_quantity)
        self.reportlist = self.reportlist + [[self.dtime, report_t]]


    def send_report(self):
        i = 0
        while i < len(self.reportlist) :
            if self.dtime >= self.reportlist[i][0] + self.delay :
                report_t = self.reportlist[i][1] 
                self.strategy.onReportEvent(report_t)
                del self.reportlist[i]
            else :
                i = i + 1


    def start(self):

        tt = time.time()
        
        for i in tqdm(range(len(self.data))) :

            self.dtime = self.data.loc[i, 'txtime']
            self.send_report()
            if self.data.loc[i, 'bid1'] > 0 or self.data.loc[i, 'ask1'] > 0:
                self.check_order_fill_by_lob(i)
                self.send_lob(i)
                self.update_lob(i)
            if self.data.loc[i, 'tick'] > 0 :
                self.check_order_fill_by_tick(i)
                self.send_tick(i)
            self.strategy.time_dependent_event()
            self.check_order()

            if time.time() > tt :
                print(f"SIM TIME {self.dtime}")
                tt = tt + 10

        self.dtime = 999999999 # 送出所有未送的 Report
        self.send_report()

    def get_profit(self):
        pass
    def get_cost(self):
        pass
    def get_return(self):
        pass

def sim_range(start_date, end_date, result_path, sid):
    cur_day = start_date
    ONEDAY = dt.timedelta(days = 1)
    while cur_day != end_date + ONEDAY:
        d_str = str(cur_day)
        d_str = d_str[:(d_str.find(" "))]
        d_str = d_str.replace("-", "")  
        filename = d_str + '_adj.csv'
        if os.path.exists(filename):
            s25 = YY25('YY25', '', 0, 0, 1, True, 'sim', beta=1, gamma=25, theta=1, position_max_q=10, qty_bound=50, weighted_factor=50, sid=sid)
            sim = simulator(s25, filename, 150)
            sim.start()
            p = sim.get_profit()
            c = sim.get_cost()
            r = sim.get_return()
            print(d_str, sid, p, c, r, file = open(result_path, "a"))
        cur_day += ONEDAY

if __name__ == "__main__":
    #st = sibs('sibs', '', 0, 0, '1', True, 'sim')
    # st = snds('snds', '', 0, 0, '1', True, 'sim')
    # st = sots('sots_t2',  '', 0, 0, 1, True, 'sim')

    s26 = YY26('YY26', '', 0, 0, 1, True, 'sim', beta=1, gamma=25, theta=1, position_max_q=10, qty_bound=50, weighted_factor=50, sid='2412')
    sim = simulator(s26, '20201104_adj.csv', 150)

    sim.start()
    s26.show_result()
