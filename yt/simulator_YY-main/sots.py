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

from docopt import docopt
import socket
import struct
import time
import numpy as np
import pandas as pd
import psycopg2
from base_strategy import base_strategy
import sots_params as params

class sots(base_strategy):

    def __init__(self, st_name, HOST, ROUTER_PORT, JASPER_PORT, partition, nodate=False, mode='trade'):
        super().__init__(st_name, HOST, ROUTER_PORT, JASPER_PORT, mode)
        self.st_name = 'sots_t2'
        self.status = 'running'
        self.partition = partition # 每50檔股票使用一個程式
        self.tlist_sql = params.sql_get_tlist
        if mode=='sim' :
            self.sleep_time = 0
        else:
            self.sleep_time = 0.0001
        if nodate :
            self.tlist_sql = self.tlist_sql.replace("= current_date", ">= '20010101'")
        self.get_trade_list(self.tlist_sql)
        self.time_now = 0
        self.exit1_done = 0
        self.exit2_done = 0
        self.hbn = [[] for i in range(len(self.tlist))]
        self.hbv = [[] for i in range(len(self.tlist))]
        self.reg_lob(list(self.tlist['sid']))
        self.reg_tick(list(self.tlist['sid']))

    def get_trade_list(self, tsql):

        conn = psycopg2.connect(dbname=params.db_name,
                                host=params.db_host,
                                port=params.db_port,
                                user=params.db_user, 
                                password=params.db_pwd)
        cur = conn.cursor()
        cur.execute(tsql)
        tlist = cur.fetchall()
        colnames = [desc[0] for desc in cur.description]
        cur.close()
        conn.close()
        tlist = pd.DataFrame(data=tlist, columns=colnames)
        tlist = tlist.astype({'sid':'str', 'minp':'float', 'maxp':'float'})
        tlist = tlist[(self.partition-1)*50:self.partition*50].reset_index(drop=True)
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
        print(list(tlist['sid']))
        self.tlist = tlist
        print("tlist", tlist)
        exit()

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
            status = self.tlist.loc[t_i, 'status']
            if status==1 and self.exit1_done==0:  # 尚未進入exit1(只出不掛)
                self.s1_lob_check(t_i) # HIT判斷
            elif status==2 :
                self.s2_lob_check(t_i) # 停損檢查


    def onTickEvent(self, payload):
        txtime, seq, prod_code, sid, price, vol,\
        match_time, acc_qty, index, total, reserved = struct.unpack('IIQ24sddIIIII', payload[:76])
        if (reserved&128)==0 and (reserved&4)==0 : #盤中
            sid = sid.decode('utf-8').replace('\x00', '').replace(' ', '')
            t_i = self.tlist.index[self.tlist['sid']==sid].tolist()
            if len(t_i)>0 :
                t_i = t_i[0]
                ask1 = self.tlist.loc[t_i, 'ask1']
                self.total_trade_p += price * tick_row['qty'] 
                self.total_trade_q += tick_row['qty'] 

                # 各股票開盤後，須累積至少 ob_tick_n 筆成交才會開始判斷是否掛單
                if len(self.hbv[t_i]) >= params.ob_tick_n :
                    self.hbn[t_i].pop(0)
                    self.hbv[t_i].pop(0)
                if price >= ask1 : # hit ask
                    self.hbv[t_i].append(0)
                    self.hbn[t_i].append(0)
                elif price < ask1 : # hit bid
                    self.hbv[t_i].append(vol)
                    self.hbn[t_i].append(1)
                    if len(self.hbv[t_i]) >= params.ob_tick_n :
                        status = self.tlist.loc[t_i, 'status']
                        if status<=1 and self.exit1_done==0: # 尚未進入exit1(只出不掛)
                            self.s01_tick_check(t_i) # 判斷是否掛單


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


    def s01_tick_check(self, t_i): # 所有掛單動作都在這裡
        status = self.tlist.loc[t_i, 'status']
        sid = self.tlist.loc[t_i, 'sid']
        bid1 = self.tlist.loc[t_i, 'bid1']
        ask1 = self.tlist.loc[t_i, 'ask1']
        bidv1 = self.tlist.loc[t_i, 'bidv1']
        bidv2 = self.tlist.loc[t_i, 'bidv2']
        maxp = self.tlist.loc[t_i, 'maxp']
        minp = self.tlist.loc[t_i, 'minp']
        ts = self.tlist.loc[t_i, 'ts']
        spread = np.ceil((ask1-bid1)/ts)
        if status == 1 : # 已有掛單者 修正bidv2
            bidv2 = bidv2 - self.tlist.loc[t_i, 'hv']
        avgbidv1 = self.tlist.loc[t_i, 'avgbidv1']
        thbn = sum(self.hbn[t_i])
        thbv = sum(self.hbv[t_i])

        if ask1 > 0 and bid1 > 0 and \
           spread <= params.max_spread and \
           thbn >= params.hit_bid_n and \
           thbv >= avgbidv1 * params.hit_bid_vr and \
           bidv2 <= avgbidv1 * params.bidv21r and \
           ask1 <= (maxp-10*ts) and bid1 >= (minp+ts) : # ask1距離漲停還有10個tick, bid1距離跌停還有一個tick

            hp = bid1 - ts
            hv = min(avgbidv1 * params.hv_avgbidv1, bidv1 * params.hv_bidv1, 100, 1000/hp) # 不超過100張, 不超過100萬
            hv = np.floor(max(1, hv)) # 最少1張
            pl = (bid1-hp-bid1*params.cost)*hv

            if pl > 0 :
                if status == 0 :
                    print(f'HANG {sid} B {hv} @ {hp}')
                    self.s_limit_rod(sid, 'B', hv, hp, t_i + 10000) # 掛單者+10000
                    self.tlist.loc[t_i, 'status'] = 1
                    self.tlist.loc[t_i, 'hv'] = hv
                    self.tlist.loc[t_i, 'hp'] = hp
                    self.tlist.loc[t_i, 'hbid1'] = bid1 # 掛單時的 bid1
                    self.tlist.loc[t_i, 'h_sl_ask1'] = hp + ts * 5 # s2 時的停損價格

                '''
                elif status == 1 : # 已有掛單且尚未hit
                    old_hv = self.tlist.loc[t_i, 'hv']
                    if hv >= old_hv * 1.5 : # 新單量大很多，重掛
                        oid = self.tlist.loc[t_i, 'oid']
                        self.s_cancel_order(oid, sid, 'B')
                        print(f'CANCEL HANG {sid} - {oid}, old_hv({old_hv}) new_hv({hv})')
                        self.s_limit_rod(sid, 'B', hv, hp, t_i+10000) # 掛單者+10000
                        print(f'HANG {sid} B {hv} @ {hp}')
                        self.tlist.loc[t_i, 'hv'] = hv
                        self.tlist.loc[t_i, 'hp'] = hp
                '''
                # s1 這裡只處理可掛量變大造成的重掛
                # 可掛量變小(須馬上hit) 以及 價位變動(須重掛) 都在 s1_lob_check
                # 且s1_lob_check只取消，不重掛


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
            else :
                print(f'NEW CONFIRM {sid} {side} {vol} @ {price} - {order_id}')
        elif report_status == 2 :
            print(f'CANCEL CONFIRM {sid} - {order_id}')
        elif report_status == 3 :
            print(f'REPLACE CONFIRM {sid} {side} {vol} @ {price}')
        elif report_status == 4 : # 完全成交
            print(f'FILL {sid} {side} {filled_quantity} @ {price} - {order_id}')
            if side == 'B':
                self.tlist.loc[t_i, 'oi'] = self.tlist.loc[t_i, 'oi'] + filled_quantity
            elif side == 'S':
                self.tlist.loc[t_i, 'oi'] = self.tlist.loc[t_i, 'oi'] - filled_quantity
            if msg_id >= 10000 : # 確認掛單完全成交
                self.tlist.loc[t_i, 'status'] = 0
                self.tlist.loc[t_i, 'oid'] = ''
                if self.tlist.loc[t_i, 'oi']!=0 :
                    self.cover_oi(t_i)
                    print(f'COVER {sid}, UNEXPECTED OI (fill report)')
                print(self.tlist.loc[self.tlist['status']!=0, ['sid', 'status', 'oi', 'hp', 'hv']])
        elif report_status == 5 : # 部分成交
            if side == 'B':
                self.tlist.loc[t_i, 'oi'] = self.tlist.loc[t_i, 'oi'] + filled_quantity
            elif side == 'S':
                self.tlist.loc[t_i, 'oi'] = self.tlist.loc[t_i, 'oi'] - filled_quantity
            print(f'PARTIAL_FILL {sid} {side} {filled_quantity} @ {price} - {order_id}')
        elif report_status == 6 :
            print(f'CANCEL_REJECT {sid} {side} - {order_id}')
        elif report_status == 7 :
            print(f'NEW_REJECT {sid} {side} {vol} @ {price}')
        elif report_status == 8 :
            print(f'REPLACE_REJECT {sid} {side} {vol} @ {price}')


    def exit_1(self):
        print('START EXIT 1')
        print(self.tlist.loc[self.tlist['status']!=0, ['sid', 'status', 'oi', 'hp', 'hv']])

        for t_i in range(len(self.tlist)) :
            status = self.tlist.loc[t_i, 'status']
            sid = self.tlist.loc[t_i, 'sid']
            oid = self.tlist.loc[t_i, 'oid']
            oi = self.tlist.loc[t_i, 'oi']
            if status==1 and oid!='' :
                self.s_cancel_order(oid, sid, 'B')
                print(f'CANCEL HANG {sid} - {oid}, EXIT_1')
                self.tlist.loc[t_i, 'oid'] = ''
                self.tlist.loc[t_i, 'status'] = 0


    def exit_2(self):
        print('START EXIT 2')
        print(self.tlist.loc[self.tlist['status']!=0, ['sid', 'status', 'oi', 'hp', 'hv']])

        for t_i in range(len(self.tlist)) :
            status = self.tlist.loc[t_i, 'status']
            sid = self.tlist.loc[t_i, 'sid']
            oid = self.tlist.loc[t_i, 'oid']
            oi = self.tlist.loc[t_i, 'oi']
            if status>0 and oid!='' :
                self.s_cancel_order(oid, sid, 'B')
                print(f'CANCEL HANG {sid} - {oid}, EXIT_2')
                self.tlist.loc[t_i, 'oid'] = ''
                self.tlist.loc[t_i, 'status'] = 0
            if oi!=0 :
                self.cover_oi(t_i)
                print(f'COVER {sid}, EXIT_2')
                self.tlist.loc[t_i, 'oid'] = ''
                self.tlist.loc[t_i, 'status'] = 0
            

    def time_dependent_event(self):

        if self.time_now>=131500000 and self.exit1_done==0 :
            self.exit1_done = 1                    
            self.exit_1()
        
        if self.time_now>=132400000 and self.exit2_done==0 :
            self.exit2_done = 1
            self.exit_2()
            self.tlist.to_csv('result.csv', index=False)
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