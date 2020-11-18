import socket
import struct
import time
import numpy as np
import pandas as pd


class base_strategy:
    
    def __init__(self, st_name, HOST, ROUTER_PORT, JASPER_PORT, mode='trade'):
        self.st_name = st_name
        self.mode = mode
        self.lob_slist = []
        self.tick_slist = []
        self.order_list = []
        if mode == 'trade' :
            self.router = self.connect_router(HOST, ROUTER_PORT)
            self.jasper = self.connect_jasper(HOST, JASPER_PORT)

    def connect_router(self, HOST, ROUTER_PORT):
        regStr = str.encode(f'REG STRATEGY {self.st_name}')
        reg = struct.pack(f'II{len(regStr)}s', 0, len(regStr), regStr)
        router = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        router.connect((HOST, ROUTER_PORT))
        router.setblocking(False)
        router.send(reg)
        return(router)

    def connect_jasper(self, HOST, JASPER_PORT):
        jasper = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        jasper.connect((HOST, JASPER_PORT))
        jasper.setblocking(False)
        return(jasper)


    def reg_lob(self, slist):
        if self.mode == 'sim' :
            self.lob_slist = slist
        else :
            for sid in slist:
                subStr = str.encode(f'SUB LOB {sid}')
                sub = struct.pack(f'II{len(subStr)}s', 0, len(subStr), subStr)
                self.router.send(sub)
                time.sleep(0.01)

    def reg_tick(self, slist):
        if self.mode == 'sim' :
            self.tick_slist = slist
        else :
            for sid in slist:
                subStr = str.encode(f'SUB TICK {sid}')
                sub = struct.pack(f'II{len(subStr)}s', 0, len(subStr), subStr)
                self.router.send(sub)
                time.sleep(0.01)


    def onTickEvent(self, payload):
        pass

    def onLobEvent(self, payload):
        pass 

    def buy_ioc(self, sid, price, vol, msg_id=0):
        self.s_new_order(5, sid, 'B', vol, price, msg_id)

    def sell_ioc(self, sid, price, vol, msg_id=0):
        self.s_new_order(5, sid, 'S', vol, price, msg_id)

    def buy_rod(self, sid, price, vol, msg_id=0):
        self.s_new_order(4, sid, 'B', vol, price, msg_id)

    def sell_rod(self, sid, price, vol, msg_id=0):
        self.s_new_order(4, sid, 'S', vol, price, msg_id)

    def s_market_rod(self, sid, BS, vol, msg_id=0):
        self.s_new_order(7, sid, BS, vol, 0, msg_id)
 
    def s_limit_rod(self, sid, BS, vol, price, msg_id=0):
        self.s_new_order(4, sid, BS, vol, price, msg_id)

    def s_new_order(self, order_option_t, sid, BS, vol, price, msg_id=0):
        # order_option_t
        # NONE = 0, SPEEDY_TIF_ROD = 1, SPEEDY_TIF_IOC = 2, SPEEDY_TIF_FOK = 3, JASPER_REG_ROD = 4,
        # JASPER_REG_IOC = 5,JASPER_REG_FOK = 6,JASPER_MKT_ROD = 7,JASPER_MKT_IOC = 8,JASPER_MKT_FOK = 9
        #print(f'SEND ORDER {sid} {BS} {vol} @ {price}')
        if BS=='B': side_t = 1
        elif BS=='S': side_t = 2
        # side_t : NONE = 0, BUY = 1, SELL = 2
        order_type = 5 
        order_len = 104
        symbol = sid
        strategy_name = self.st_name
        order_id = ''
        quantity = int(vol)
        price = float(price)
        market_t = 2 # NONE = 0, TAIFEX = 1, TWSE = 2, 
        # msg_id = 0 # int32
        action_t = 1 # NONE = 0, NEW = 1, REPLACE_PRICE = 2, REDUCT_QTY = 3, CANCEL = 4
        order_mode_t = 0 # NONE = 0, SPEEDY_LIMIT = 1, SPEEDY_MARKET = 2, JASPER_REGULAR = 3, JASPER_MARGIN = 4
        unuse = 0
        
        # 一張單最多下400張
        o_round = int(np.ceil(vol/400))
        lastv = int(vol%400)
        if lastv == 0 : lastv = 400
        for i in range(1, o_round+1) :
            if i < o_round :
                quantity = 400
            elif i == o_round :
                quantity = lastv
            order_t = struct.pack('II20s20s24sIIdIiIIII', order_type, order_len,\
                                  str.encode(symbol), str.encode(strategy_name), str.encode(order_id),\
                                  side_t, quantity, price, market_t, msg_id, action_t,\
                                  order_mode_t, order_option_t, unuse)

            if self.mode == 'sim' :
                self.order_list = self.order_list + [order_t]
            else :
                self.jasper.send(order_t)


    def s_adj_order_vol(self, order_id, sid, BS, reduce_qty, msg_id=0):
        if BS=='B': side_t = 1
        elif BS=='S': side_t = 2
        order_option_t = 0
        order_type = 5 
        order_len = 104
        symbol = sid
        strategy_name = self.st_name
        # order_id = order_id # str
        quantity = int(reduce_qty)
        price = 0
        market_t = 2 # NONE = 0, TAIFEX = 1, TWSE = 2
        # msg_id = 0 # int32
        action_t = 3 # NONE = 0, NEW = 1, REPLACE_PRICE = 2, REDUCT_QTY = 3, CANCEL = 4
        order_mode_t = 0 # NONE = 0, SPEEDY_LIMIT = 1, SPEEDY_MARKET = 2, JASPER_REGULAR = 3, JASPER_MARGIN = 4
        unuse = 0
        order_t = struct.pack('II20s20s24sIIdIiIIII', order_type, order_len,\
                              str.encode(symbol), str.encode(strategy_name), str.encode(order_id),\
                              side_t, quantity, price, market_t, msg_id, action_t,\
                              order_mode_t, order_option_t, unuse)
        if self.mode == 'sim' :
            self.order_list = self.order_list + [order_t]
        else :
            self.jasper.send(order_t)


    def s_cancel_order(self, order_id, sid, BS, msg_id=0):
        if BS=='B': side_t = 1
        elif BS=='S': side_t = 2 # side_t NONE = 0, BUY = 1, SELL = 2
        order_option_t = 0
        order_type = 5 
        order_len = 104
        symbol = sid
        strategy_name = self.st_name
        # order_id = order_id
        quantity = 0
        price = 0
        market_t = 2 # NONE = 0, TAIFEX = 1, TWSE = 2
        # msg_id = 0 # int32
        action_t = 4 # NONE = 0, NEW = 1, REPLACE_PRICE = 2, REDUCT_QTY = 3, CANCEL = 4
        order_mode_t = 0 # NONE = 0, SPEEDY_LIMIT = 1, SPEEDY_MARKET = 2, JASPER_REGULAR = 3, JASPER_MARGIN = 4
        unuse = 0
        order_t = struct.pack('II20s20s24sIIdIiIIII', order_type, order_len,\
                              str.encode(symbol), str.encode(strategy_name), str.encode(order_id),\
                              side_t, quantity, price, market_t, msg_id, action_t,\
                              order_mode_t, order_option_t, unuse)
        if self.mode == 'sim' :
            self.order_list = self.order_list + [order_t]
        else :
            self.jasper.send(order_t)