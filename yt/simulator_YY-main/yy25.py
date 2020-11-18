"""
Usage:
    sots.py (-h | --help)
    sots.py [-p <partition> --nodate --sim]

Options:
    -h --help   Show this screen.
    -p <partition>    Partition of all trading stock list [default: 1].
    --nodate    Remove SQL trading date constraint.
    --sim    Simulator router and jasper port. 
"""
import matplotlib.pyplot as plt
from docopt import docopt
import socket
import struct
import time
import numpy as np
import pandas as pd
import psycopg2
from base_strategy import base_strategy
import sots_params as params

class YY25(base_strategy):
    def __init__(self, st_name, HOST, ROUTER_PORT, JASPER_PORT, partition, nodate, mode, beta, gamma, theta, position_max_q, qty_bound, weighted_factor, sid):

    # def __init__(self, st_name, HOST, ROUTER_PORT, JASPER_PORT, partition, nodate=False, mode='trade'):
        super().__init__(st_name, HOST, ROUTER_PORT, JASPER_PORT, mode)
        self.st_name = 'YY25'
        self.status = 'running'
        self.partition = partition # 每50檔股票使用一個程式
        self.tlist_sql = params.sql_get_tlist
        self.sid = sid

        if mode=='sim' :
            self.sleep_time = 0
        else:
            self.sleep_time = 0.0001
        if nodate :
            self.tlist_sql = self.tlist_sql.replace("= current_date", ">= '20010101'")

        self.get_trade_list(self.tlist_sql)
        self.time_now = 0
        self.reg_lob(list(self.tlist['sid']))
        self.reg_tick(list(self.tlist['sid']))

        self.num_buy = 0
        self.num_sell = 0
        self.profit = 0
        self.cost = 0
        self.position = []
        self.current_time = 0
        self.total_cost = 0
        self.exit_cancel_order_done = False
        
        self.exit_clean_position_done = 0
        self.exit2_done = 0

        self.tick_list_buy_sell = []
        self.tick_list_weight_p = []
        self.beta = beta
        
        self.order_long_p = np.array([])
        self.order_long_q = np.array([], dtype = "int32")
        self.order_short_p = np.array([])
        self.order_short_q = np.array([], dtype = "int32")
        self.order_short_oid = np.array([], dtype = "<U3")
        self.order_long_oid = np.array([], dtype = "<U3")
        self.waiting_long_queue = np.array([], dtype = "int32")
        self.waiting_short_queue = np.array([], dtype = "int32")
        self.gamma = gamma
        self.sell_history = []
        self.buy_history = []
        self.sell_time = []
        self.buy_time = []
        self.bid1_p = 0
        self.bid1_q = 0
        self.ask1_p = 0
        self.ask1_q = 0
        
        self.theta = theta
        self.weighted_p = 0
        self.total_trade_q = 0
        self.total_trade_p = 0
        self.position_max_q = position_max_q
        self.position = np.array([])
        # self.position_q = np.array([], dtype = "int32")
        self.position_q = 0
        self.weighted_p_list = []
        self.weighted_p_time_list = []
        self.sell_buy_time_list = []
        self.sell_buy_ratio_list = []
        self.qty_bound = qty_bound
        self.weighted_factor = weighted_factor
        self.wish_p_list = np.array([])
        self.wish_q_list = np.array([])
        self.wish_time_list = np.array([])
        self.wish_corres_list = np.array([])
        self.buy_p = np.array([])
        self.buy_q = np.array([])
        self.sell_p =np.array([])
        self.sell_q =np.array([])
    
    def numtotime(self, num):
        ms = num % 1000
        num //= 1000
        s = num % 100
        num //= 100
        mi = num % 100
        num //= 100
        h = num % 100
        num = num // 100
    # print(h, mi, s, ms)
        return dt.datetime(2020, 9, 21, h, mi, s, ms) # TODO

    def get_trade_list(self, tsql):

        tlist = pd.DataFrame(data={"sid": [self.sid], 'minp':[0], "maxp":[100]})
        # self.tlist.loc[0, "sid"]
        tlist['bid1'] = 0
        tlist['bid2'] = 0
        tlist['bidv1'] = 0
        tlist['bidv2'] = 0
        tlist['ask1'] = 0
        tlist['askv1'] = 0
        tlist['ts'] = 0
        tlist['oi'] = 0
        tlist['oid'] = ''
        tlist['hv'] = 0
        tlist['hp'] = 0
        tlist['hbid1'] = 0 # 掛單當時的bid1
        tlist['h_sl_aks1'] = 0 # s2時的停損位置
        tlist['lobn'] = 0
        tlist['avgbidv1'] = 0
        tlist['status'] = 0
        self.tlist = tlist


        print(list(self.tlist['sid']))

        # exit()
    def onLobEvent(self, payload):
        txtime, seq, prod_code, sid, num_bid, num_ask, \
        bid1, bidv1, bid2, bidv2, bid3, bidv3, bid4, bidv4, bid5, bidv5, \
        ask1, askv1, ask2, askv2, ask3, askv3, ask4, askv4, ask5, askv5 \
        = struct.unpack('IIQ24sIIdddddddddddddddddddd', payload[:208])
        self.time_now = txtime
        sid = sid.decode('utf-8').replace('\x00', '').replace(' ', '')
        t_i = self.tlist.index[self.tlist['sid']==sid].tolist()

        if len(t_i)>0 :
            t_i = t_i[0]
            lobn = self.tlist.loc[t_i, 'lobn']
            self.tlist.loc[t_i, 'avgbidv1'] = (self.tlist.loc[t_i, 'avgbidv1'] * lobn + bidv1) / (lobn + 1)
            self.tlist.loc[t_i, 'lobn'] = lobn + 1
            self.tlist.loc[t_i, 'ask1'] = ask1
            self.tlist.loc[t_i, 'bid1'] = bid1
            self.tlist.loc[t_i, 'bidv1'] = bidv1
            self.tlist.loc[t_i, 'bid2'] = bid2
            self.tlist.loc[t_i, 'bidv2'] = bidv2
            self.tlist.loc[t_i, 'ts'] = self.tick_size(bid1)
            self.bid1_p = bid1
            self.bid1_q = bidv1
            self.ask1_p = ask1
            self.ask1_q = askv1
            status = self.tlist.loc[t_i, 'status']
            if self.exit_clean_position_done ==0:  # 尚未進入exit1(只出不掛)
               self.could_order(t_i) 
               self.could_cancel_order(t_i) 
            #     self.s1_lob_check(t_i) # HIT判斷
            # elif status==2 :
            #     self.s2_lob_check(t_i) # 停損檢查


    def onTickEvent(self, payload):
        txtime, seq, prod_code, sid, price, qty,\
        match_time, acc_qty, index, total, reserved = struct.unpack('IIQ24sddIIIII', payload[:76])

        self.time_now = txtime

        if (reserved&128)==0 and (reserved&4)==0 : #盤中
            sid = sid.decode('utf-8').replace('\x00', '').replace(' ', '')
            t_i = self.tlist.index[self.tlist['sid']==sid].tolist()
            if len(t_i)>0 :
                t_i = t_i[0]
                ask1 = self.tlist.loc[t_i, 'ask1']
                

                self.total_trade_p += price * qty 
                self.total_trade_q += qty 


                # 各股票開盤後，須累積至少 ob_tick_n 筆成交才會開始判斷是否掛單
                # if len(self.hbv[t_i]) >= params.ob_tick_n :
                #     self.hbn[t_i].pop(0)
                #     self.hbv[t_i].pop(0)
                # if price >= ask1 : # hit ask
                #     self.hbv[t_i].append(0)
                #     self.hbn[t_i].append(0)
                # elif price < ask1 : # hit bid
                #     self.hbv[t_i].append(vol)
                #     self.hbn[t_i].append(1)
                #     if len(self.hbv[t_i]) >= params.ob_tick_n :
                #         status = self.tlist.loc[t_i, 'status']
                #         if status<=1 and self.exit1_done==0: # 尚未進入exit1(只出不掛)
                #             self.s01_tick_check(t_i) # 判斷是否掛單
                if len(self.tick_list_weight_p) < self.weighted_factor:
                    self.tick_list_weight_p.append({"price": price, "qty":qty})
                else:
                    self.total_trade_p -= self.tick_list_weight_p[0]['price'] * self.tick_list_weight_p[0]['qty'] 
                    self.total_trade_q -= self.tick_list_weight_p[0]['qty']
                    self.tick_list_weight_p.pop(0)
                    self.tick_list_weight_p.append({"price": price, "qty":qty})
                    self.weighted_p = self.total_trade_p / self.total_trade_q
                    self.weighted_p_list.append(self.weighted_p)
                    self.weighted_p_time_list.append(self.time_now)
                ########################################


    def s1_lob_check(self, t_i): # 判斷是否hit以及是否取消掛單
        hp = self.tlist.loc[t_i, 'hp']
        hv = self.tlist.loc[t_i, 'hv']
        hbid1 = self.tlist.loc[t_i, 'hbid1']
        bid1 = self.tlist.loc[t_i, 'bid1']
        bidv1 = self.tlist.loc[t_i, 'bidv1']
        sid = self.tlist.loc[t_i, 'sid']
        minp = self.tlist.loc[t_i, 'minp']
        oid = self.tlist.loc[t_i, 'oid']
        oi = self.tlist.loc[t_i, 'oi']

        if bid1 == hbid1 : # bid1 與掛單時相同
            if bidv1 <= np.ceil(hv * params.hit_entry_r) : # 該 hit 了
                if bidv1 < hv and oid != '' : # bid1 量不足時
                    print(f'VOL_ADJ {sid}, bidv1({bidv1}) < hv({hv})')
                    reduce_qty = hv - bidv1
                    self.s_adj_order_vol(oid, sid, 'B', reduce_qty)
                    print(f'HIT {sid} {bidv1}')
                    self.s_limit_rod(sid, 'S', bidv1, minp, t_i)
                    self.tlist.loc[t_i, 'status'] = 2
                else :
                    print(f'HIT {sid} {hv}')
                    self.s_limit_rod(sid, 'S', hv, minp, t_i)
                    self.tlist.loc[t_i, 'status'] = 2
        else :
            # bid1 已與 掛單時不一樣
            # s1時，bid1整個被大單吃掉時，立刻取消掛單 (bid2掛單可能已經被hit，需檢查oi)
            # s1時，bid1已經往上移，掛單已非bid2，立刻取消掛單
            if oid != '' :
                self.s_cancel_order(oid, sid, 'B')
                print(f'CANCEL HANG {sid} - {oid}, bid1({bid1}) hbid1({hbid1}) hp({hp})')
                self.tlist.loc[t_i, 'status'] = 0
                self.tlist.loc[t_i, 'oid'] = ''
                if oi != 0 :
                    self.cover_oi(t_i)
                    print(f'COVER {sid}, UNEXPECTED OI (s1 lob check)')


    def s2_lob_check(self, t_i):
        sid = self.tlist.loc[t_i, 'sid']
        oid = self.tlist.loc[t_i, 'oid']
        ask1 = self.tlist.loc[t_i, 'ask1']
        hp = self.tlist.loc[t_i, 'hp']
        h_sl_ask1 = self.tlist.loc[t_i, 'h_sl_ask1']
        if ask1 >= h_sl_ask1 and oid != '':
            print(f'STOP LOSS {sid}, ask1({ask1}) hp({hp}) sl_ask1({h_sl_ask1})')
            self.s_cancel_order(oid, sid, 'B')
            print(f'CANCEL HANG {sid} - {oid}, STOPLOSS')
            self.cover_oi(t_i)
            print(f'COVER {sid}, STOPLOSS')
            self.tlist.loc[t_i, 'oid'] = ''
            self.tlist.loc[t_i, 'status'] = 0


    def cover_oi(self, t_i):
        sid = self.tlist.loc[t_i, 'sid']
        oi = self.tlist.loc[t_i, 'oi']
        if oi > 0 :
            self.s_limit_rod(sid, 'S', oi, self.tlist.loc[t_i, 'minp'], t_i)
        elif oi < 0 :
            self.s_limit_rod(sid, 'B', -oi, self.tlist.loc[t_i, 'maxp'], t_i)


    # def s01_tick_check(self, t_i): # 所有掛單動作都在這裡
    #     status = self.tlist.loc[t_i, 'status']
    #     sid = self.tlist.loc[t_i, 'sid']
    #     bid1 = self.tlist.loc[t_i, 'bid1']
    #     ask1 = self.tlist.loc[t_i, 'ask1']
    #     bidv1 = self.tlist.loc[t_i, 'bidv1']
    #     bidv2 = self.tlist.loc[t_i, 'bidv2']
    #     maxp = self.tlist.loc[t_i, 'maxp']
    #     minp = self.tlist.loc[t_i, 'minp']
    #     ts = self.tlist.loc[t_i, 'ts']
    #     spread = np.ceil((ask1-bid1)/ts)
    #     if status == 1 : # 已有掛單者 修正bidv2
    #         bidv2 = bidv2 - self.tlist.loc[t_i, 'hv']
    #     avgbidv1 = self.tlist.loc[t_i, 'avgbidv1']
    #     thbn = sum(self.hbn[t_i])
    #     thbv = sum(self.hbv[t_i])

    #     if ask1 > 0 and bid1 > 0 and \
    #        spread <= params.max_spread and \
    #        thbn >= params.hit_bid_n and \
    #        thbv >= avgbidv1 * params.hit_bid_vr and \
    #        bidv2 <= avgbidv1 * params.bidv21r and \
    #        ask1 <= (maxp-10*ts) and bid1 >= (minp+ts) : # ask1距離漲停還有10個tick, bid1距離跌停還有一個tick

    #         hp = bid1 - ts
    #         hv = min(avgbidv1 * params.hv_avgbidv1, bidv1 * params.hv_bidv1, 100, 1000/hp) # 不超過100張, 不超過100萬
    #         hv = np.floor(max(1, hv)) # 最少1張
    #         pl = (bid1-hp-bid1*params.cost)*hv

    #         if pl > 0 :
    #             if status == 0 :
    #                 print(f'HANG {sid} B {hv} @ {hp}')
    #                 self.s_limit_rod(sid, 'B', hv, hp, t_i + 10000) # 掛單者+10000
    #                 self.tlist.loc[t_i, 'status'] = 1
    #                 self.tlist.loc[t_i, 'hv'] = hv
    #                 self.tlist.loc[t_i, 'hp'] = hp
    #                 self.tlist.loc[t_i, 'hbid1'] = bid1 # 掛單時的 bid1
    #                 self.tlist.loc[t_i, 'h_sl_ask1'] = hp + ts * 5 # s2 時的停損價格

    #             '''
    #             elif status == 1 : # 已有掛單且尚未hit
    #                 old_hv = self.tlist.loc[t_i, 'hv']
    #                 if hv >= old_hv * 1.5 : # 新單量大很多，重掛
    #                     oid = self.tlist.loc[t_i, 'oid']
    #                     self.s_cancel_order(oid, sid, 'B')
    #                     print(f'CANCEL HANG {sid} - {oid}, old_hv({old_hv}) new_hv({hv})')
    #                     self.s_limit_rod(sid, 'B', hv, hp, t_i+10000) # 掛單者+10000
    #                     print(f'HANG {sid} B {hv} @ {hp}')
    #                     self.tlist.loc[t_i, 'hv'] = hv
    #                     self.tlist.loc[t_i, 'hp'] = hp
    #             '''
    #             # s1 這裡只處理可掛量變大造成的重掛
    #             # 可掛量變小(須馬上hit) 以及 價位變動(須重掛) 都在 s1_lob_check
    #             # 且s1_lob_check只取消，不重掛



    def tick_size(self, p):
        # sots 掛單是往下掛 故等號在大的一方
        if p<=10 :
            ts = 0.01
        elif p>10 and p<=50 :
            ts = 0.05
        elif p>50 and p<=100 :
            ts = 0.1
        elif p>100 and p<=500 :
            ts = 0.5
        elif p>500 and p<=1000 :
            ts = 1
        elif p>1000 :
            ts = 5
        return(ts)



    def onReportEvent(self, payload):
        sid, st_name, order_id, side_t, vol, price, market_t, msg_id,\
        report_status, filled_quantity = struct.unpack('20s20s24sIIdIiII', payload[:96])
        sid = sid.decode('utf-8').replace('\x00', '').replace(' ', '')
        order_id = order_id.decode('utf-8').replace('\x00', '').replace(' ', '')
        msg_id = int(msg_id)
        price = round(price, 2)
        filled_quantity = int(filled_quantity)

        if side_t == 1 : 
            side = 'B'
        elif side_t == 2 : 
            side = 'S'
        else : 
            side = 'NONE'

        if msg_id >= 10000 : # 為掛單者
            t_i = msg_id - 10000
        else : # 一般下單
            t_i = msg_id 

        if report_status == 1 : # 新單確認
            if msg_id >= 10000 : # 為掛單，取回掛單的 ORDER ID
                print(f'HANG CONFIRM {sid} {side} {vol} @ {price} - {order_id}')
                self.tlist.loc[t_i, 'oid'] = order_id
                self.s1_lob_check(t_i) # 掛單成功後馬上做一次 lob check
                if side == 'B':
                    self.order_long_p = np.append(self.order_long_p, price)
                    self.order_long_q = np.append(self.order_long_q, vol)
                    self.order_long_oid = np.append(self.order_long_oid, order_id)
                    # print("type of oid: ", type(order_id), "order_id", order_id)
                    # print("order_long_oid: ", self.order_long_oid)
                if side == 'S':
                    self.order_short_p = np.append(self.order_short_p, price)
                    self.order_short_q = np.append(self.order_short_q, vol)
                    self.order_short_oid = np.append(self.order_short_oid, order_id)
                    # print("type of oid: ", type(order_id), "order_id", order_id)
                    # print("order_short_oid: ", self.order_short_oid)

            else :
                print(f'NEW CONFIRM {sid} {side} {vol} @ {price} - {order_id}')
                print("confirm time: ", self.time_now)
                print("### weighted_p: ", self.weighted_p)
                if side == 'B':
                    self.order_long_p = np.append(self.order_long_p, price)
                    self.order_long_q = np.append(self.order_long_q, vol)
                    self.order_long_oid = np.append(self.order_long_oid, order_id)
                    # print("type of oid: ", type(order_id), "order_id", order_id)
                    # print("order_long_oid: ", self.order_long_oid)
                if side == 'S':
                    self.order_short_p = np.append(self.order_short_p, price)
                    self.order_short_q = np.append(self.order_short_q, vol)
                    self.order_short_oid = np.append(self.order_short_oid, order_id)
                    # print("type of oid: ", type(order_id), "order_id", order_id)
                    # print("order_short_oid: ", self.order_short_oid)
        elif report_status == 2 :
            if side == 'B':
                delete_index = np.argwhere(order_id ==self.order_long_oid )
                self.order_long_oid = np.delete(self.order_long_oid, delete_index)
                self.order_long_p = np.delete(self.order_long_p, delete_index)
                self.order_long_q = np.delete(self.order_long_q, delete_index)
                print(f'CANCEL CONFIRM {sid} - {order_id}')
                print("### weighted_p: ", self.weighted_p)
            
            elif side == 'S':
                delete_index = np.argwhere(order_id ==self.order_short_oid )
                self.order_short_oid = np.delete(self.order_short_oid, delete_index)
                self.order_short_p = np.delete(self.order_short_p, delete_index)
                self.order_short_q = np.delete(self.order_short_q, delete_index)
                print(f'CANCEL CONFIRM {sid} - {order_id}')
                print("### weighted_p: ", self.weighted_p)

        elif report_status == 3 :
            print(f'REPLACE CONFIRM {sid} {side} {vol} @ {price}')
        elif report_status == 4 : # 完全成交
            print(f'FILL {sid} {side} {filled_quantity} @ {price} - {order_id}')
            if side == 'B':
                self.tlist.loc[t_i, 'oi'] = self.tlist.loc[t_i, 'oi'] + filled_quantity
                self.position_q += filled_quantity
            
                self.buy_p = np.append(self.buy_p, price)
                self.buy_q = np.append(self.buy_q, filled_quantity)
                self.buy_history.append(price)
                self.buy_time.append(self.time_now)
                
                delete_index = np.argwhere(self.order_long_oid == order_id)
                self.order_long_q = np.delete(self.order_long_q, delete_index)
                self.order_long_p = np.delete(self.order_long_p, delete_index)
                self.order_long_oid = np.delete(self.order_long_oid, delete_index)

            
            elif side == 'S':
                self.position_q -= filled_quantity
                self.tlist.loc[t_i, 'oi'] = self.tlist.loc[t_i, 'oi'] - filled_quantity
                self.sell_history.append(price)
                self.sell_time.append(self.time_now)
                self.sell_p = np.append(self.sell_p, price)
                self.sell_q = np.append(self.sell_q, filled_quantity)

                delete_index = np.argwhere(self.order_short_oid == order_id)
                self.order_short_q = np.delete(self.order_short_q, delete_index)
                self.order_short_p = np.delete(self.order_short_p, delete_index)
                self.order_short_oid = np.delete(self.order_short_oid, delete_index)
            
            if msg_id >= 10000 : # 確認掛單完全成交
                self.tlist.loc[t_i, 'status'] = 0
                self.tlist.loc[t_i, 'oid'] = ''
                # if self.tlist.loc[t_i, 'oi']!=0 :
                #     self.cover_oi(t_i)
                #     print(f'COVER {sid}, UNEXPECTED OI (fill report)')
                # print(self.tlist.loc[self.tlist['status']!=0, ['sid', 'status', 'oi', 'hp', 'hv']])
        elif report_status == 5 : # 部分成交
            if side == 'B':
                self.tlist.loc[t_i, 'oi'] = self.tlist.loc[t_i, 'oi'] + filled_quantity
                self.position_q += filled_quantity
            
                self.buy_p = np.append(self.buy_p, price)
                self.buy_q = np.append(self.buy_q, filled_quantity)
                self.buy_history.append(price)
                self.buy_time.append(self.time_now)
                
                index = np.argwhere(self.order_long_oid == order_id)[0]
                self.order_long_q[index] -= filled_quantity 
            
            elif side == 'S':
                self.position_q -= filled_quantity
                self.tlist.loc[t_i, 'oi'] = self.tlist.loc[t_i, 'oi'] - filled_quantity
                self.sell_history.append(price)
                self.sell_time.append(self.time_now)
                self.sell_p = np.append(self.sell_p, price)
                self.sell_q = np.append(self.sell_q, filled_quantity)

                index = np.argwhere(self.order_short_oid == order_id)[0]
                self.order_short_q[index] -= filled_quantity 
            print(f'PARTIAL_FILL {sid} {side} {filled_quantity} @ {price} - {order_id}')
        elif report_status == 6 :
            print(f'CANCEL_REJECT {sid} {side} - {order_id}')
        elif report_status == 7 :
            print(f'NEW_REJECT {sid} {side} {vol} @ {price}')
        elif report_status == 8 :
            print(f'REPLACE_REJECT {sid} {side} {vol} @ {price}')

    def could_cancel_order(self, t_i):
        if self.time_now <= 120000000:
            if self.bid1_q < 500: 
                cancel_index = np.argwhere(self.weighted_p/1.00025 < self.order_long_p).reshape(-1)
                for i in cancel_index:
                    self.s_cancel_order(str(self.order_long_oid[i]), self.sid, "B")
            if self.ask1_q < 500:
                cancel_index = np.argwhere(self.weighted_p*1.00025 > self.order_short_p).reshape(-1)
                for i in cancel_index:
                    self.s_cancel_order(str(self.order_short_oid[i]), self.sid, "S")
            return 


    def exit_cancel_order(self):
        num_position = self.position_q
        self.exit_cancel_order_done = True
        if num_position > 0:
            # print("取消多單")
            for i in range(len(self.order_long_oid)):
                self.s_cancel_order(self.order_long_oid[i], self.sid, "B")
            
        elif num_position < 0:
            #print("取消空單")
            for i in range(len(self.order_short_oid)):
                self.s_cancel_order(self.order_short_oid[i], self.sid, "S")
        else:
            
            #print("都取消")
            for i in range(len(self.order_long_oid)):
                self.s_cancel_order(self.order_long_oid[i], self.sid, "B")
            for i in range(len(self.order_short_oid)):
                self.s_cancel_order(self.order_short_oid[i], self.sid, "S")


    def could_order(self, t_i):
        #FINDORDER
        if not 120000000 >= self.time_now >= 90000000:
            return
        num_order_bid1_q = 0
        num_order_ask1_q = 0
        num_position = self.position_q
        if self.tlist.loc[t_i, 'sid']!= self.sid:
            return
        # 在 bid1_p掛幾張了
        for i in range(len(self.order_long_p)):
            if (self.order_long_p[i] == self.bid1_p):
                num_order_bid1_q += self.order_long_q[i]
        # 在 ask1_p掛幾張了
        for i in range(len(self.order_short_p)):
            if (self.order_short_p[i] == self.ask1_p):
                num_order_ask1_q += self.order_short_q[i]
        # 出場條件
        if num_order_bid1_q < -num_position and num_position < 0\
            and self.tlist.loc[t_i, 'bid1'] < self.weighted_p:
            print("num_order_bid1_q", num_order_bid1_q , "num_position", num_position)
            print("@leave buy want to order", -num_order_bid1_q - num_position)
            self.s_new_order(4, self.sid, "B", -num_order_bid1_q - num_position, self.tlist.loc[t_i, 'bid1'], msg_id=t_i)
            # self.order(self.bid1_p, -num_order_bid1_q - num_position, etype = "BUY_QUEUE")
        # 進場條件 
        elif num_order_bid1_q < min(self.qty_bound, self.bid1_q) and self.bid1_q > self.qty_bound and abs(num_position) < self.qty_bound\
        and self.bid1_p < self.weighted_p*0.99995:
            print("qty_bound", self.qty_bound , "num_order_bid1_q", num_order_bid1_q)
            print("@in buy want to order", self.qty_bound - num_order_bid1_q)

            self.s_new_order(4, self.sid, "B", self.qty_bound - num_order_bid1_q, self.tlist.loc[t_i, 'bid1'], msg_id=t_i)
            # self.order(self.bid1_p, self.qty_bound - num_order_bid1_q, etype = "BUY_QUEUE")
        # 出場條件
        if num_order_ask1_q < num_position\
            and self.tlist.loc[t_i, 'ask1'] > self.weighted_p:
            print("-num_order_ask1_q", -num_order_ask1_q , "num_position", num_position)
            print("@leave sell want to order", -num_order_ask1_q + num_position)
            self.s_new_order(4, self.sid, "S", -num_order_ask1_q + num_position, self.tlist.loc[t_i, 'ask1'], msg_id=t_i)
            #self.order(self.ask1_p, -num_order_ask1_q + num_position, etype = "SELL_QUEUE")
        # 進場條件 
        elif num_order_ask1_q < min(self.qty_bound, self.ask1_q) and self.ask1_q > self.qty_bound and abs(num_position) < self.qty_bound\
        and self.ask1_p > self.weighted_p*1.0005:
            print("self.qty_bound", self.qty_bound, "num_order_ask1_q", num_order_ask1_q)
            print("@in sell want to order", self.qty_bound - num_order_ask1_q)
            self.s_new_order(4, self.sid, "S", self.qty_bound - num_order_ask1_q, self.tlist.loc[t_i, 'ask1'], msg_id=t_i)
            # self.order(self.ask1_p, self.qty_bound - num_order_ask1_q, etype = "SELL_QUEUE")
    def exit_clean_position(self, t_i):
        print('START EXIT 1')
        print(self.tlist.loc[self.tlist['status']!=0, ['sid', 'status', 'oi', 'hp', 'hv']])

        # for t_i in range(len(self.tlist)) :
        #     status = self.tlist.loc[t_i, 'status']
        #     sid = self.tlist.loc[t_i, 'sid']
        #     oid = self.tlist.loc[t_i, 'oid']
        #     oi = self.tlist.loc[t_i, 'oi']
        #     if status==1 and oid!='' :
        #         self.s_cancel_order(oid, sid, 'B')
        #         print(f'CANCEL HANG {sid} - {oid}, EXIT_1')
        #         self.tlist.loc[t_i, 'oid'] = ''
        #         self.tlist.loc[t_i, 'status'] = 0
        for i in self.order_long_oid:
            self.s_cancel_order(i, self.sid, "B", t_i)
        for i in self.order_short_oid:
            self.s_cancel_order(i, self.sid, "S", t_i)
        
        print("position_q", self.position_q)
        if self.position_q > 0:
            self.s_new_order(7, self.sid, "S", self.position_q, 0, msg_id=t_i)
        elif self.position_q < 0:
            self.s_new_order(7, self.sid, "B", -self.position_q, 0, msg_id=t_i)
            # self.s_new_order(7, self.sid, "B", self.position_q, 0, msg_id)




    def show_result(self):
        print("----------Result Report--------------")
        print("position_q", self.position_q)
        print("buy_p", self.buy_p)
        print("buy_q", self.buy_q)
        print("sell_p", self.sell_p)
        print("sell_q", self.sell_q)
        print("sell_q_sum", self.sell_q.sum(), "buy_q_sum", self.buy_q.sum())
        p = np.array(self.sell_p) @ np.array(self.sell_q) - np.array(self.buy_p) @ np.array(self.buy_q)
        print("profit: ", p)
        c = np.array(self.sell_p) @ np.array(self.sell_q)
        print("cost: ", np.array(self.sell_p) @ np.array(self.sell_q))
        print("r", p/c)
        exit()
        
        if len(self.buy_time):
        
            plt.figure(figsize=(20,10))
            plt.subplot(311)
            plt.title("price")
            plt.plot(self.df.index, self.df.loc[:, 'price'], label = 'price')
            plt.plot([self.numtotime(x) for x in self.weighted_p_time_list], self.weighted_p_list, label = 'weighted_p')
            plt.scatter([self.numtotime(x) for x in self.sell_time], self.sell_history, marker='v', s= 144, c="lime")
            plt.scatter([self.numtotime(x) for x in self.buy_time], self.buy_history, marker='^', s = 144, c="red")
            plt.legend()
        else:
            plt.figure(figsize=(20,10))
            plt.subplot(311)
            plt.title("price")
            plt.plot(self.df.index, self.df.loc[:, 'price'], label = 'price')
            plt.plot([self.numtotime(x) for x in self.weighted_p_time_list], self.weighted_p_list, label = 'weighted_p')
            plt.legend()
        plt.subplot(312)
        #plt.figure(figsize=(20,10))
        plt.title("q")
        plt.plot(self.df.index, self.df.loc[:, "qty"])
        plt.subplot(313)
        plt.title("sell buy ratio")
        plt.yscale("log")
        self.sell_buy_time_list.append(133000000)
        self.sell_buy_ratio_list.append(self.sell_buy_ratio_list[-1])
        plt.plot([self.numtotime(x) for x in self.sell_buy_time_list], self.sell_buy_ratio_list, label = "sell")
        plt.plot([self.numtotime(x) for x in self.sell_buy_time_list], [1/x if x != 0 else 20 for x in self.sell_buy_ratio_list], label = 'buy')
        plt.plot([self.numtotime(self.sell_buy_time_list[0]), self.numtotime(self.sell_buy_time_list[-1])], [self.beta, self.beta])
        plt.legend()


    def time_dependent_event(self):

        if self.time_now>=120000000 and self.exit_cancel_order_done == False: 
            self.exit_cancel_order()
        if self.time_now>=130000000 and self.exit_clean_position_done==0:
            self.exit_clean_position_done = 1                    
            self.exit_clean_position(0)
            # self.tlist.to_csv('result.csv', index=False)
        if self.time_now>=132300000 and self.exit_clean_position_done==1:
            self.exit_clean_position_done = 2                    
            self.exit_clean_position(0)
            self.status = 'stop'

    def start(self):

        while self.status=='running':

            self.time_dependent_event()

            try:
                header = self.router.recv(8)
                typ, plen = struct.unpack('II', header)
                payload = self.router.recv(plen)
                if typ==2 : 
                    self.onTickEvent(payload)
                if typ==3 :
                    self.onLobEvent(payload)
                
            except:
                pass
                
            try:
                header = self.jasper.recv(8)
                typ, plen = struct.unpack('II', header)
                payload = self.jasper.recv(plen)
                if typ==6 : 
                    self.onReportEvent(payload)
            except:
                pass

            time.sleep(self.sleep_time)

        print("hello world")
        self.show_result()


if __name__ == "__main__":

    t_args = docopt(__doc__)
    print(t_args)
    
    partition = int(t_args['-p'])

    if t_args['--sim'] :
        mode = 'sim'
    else :
        mode = 'trade'

    if t_args['--nodate'] :
        nodate = True
    else :
        nodate = False

    algo_sots = sots('sots_t2', params.HOST, params.ROUTER_PORT, params.JASPER_PORT, 
                     partition, nodate, mode)
    algo_sots.start()