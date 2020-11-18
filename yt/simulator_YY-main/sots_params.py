HOST = '127.0.0.1'
ROUTER_PORT = 10308
JASPER_PORT = 10310
SIM_ROUTER_PORT = 40110
SIM_JASPER_PORT = 40111

db_name = 'opsdb'
db_host = '172.22.20.28'
db_port = 5432
db_user = 'algo308'
db_pwd = 'dontabuse'

sql_get_tlist = f"""
SELECT
    SOTS.sid,
    T30.minp,
    T30.maxp
FROM tradedb.sots SOTS
INNER JOIN (
    SELECT
        c07 as sid,
        c15 as maxp,
        c16 as minp,
        c00 as txdate,
        c20 as mark_day_trade
    FROM twse.fmt1
    UNION
    SELECT
        c07 as sid,
        c15 as maxp,
        c16 as minp,
        c00 as txdate,
        c20 as mark_day_trade
    FROM tpex.fmt1
) as T30 
ON SOTS.sid = T30.sid
AND SOTS.txdate = current_date
AND T30.txdate = current_date
AND T30.mark_day_trade = 'A'
"""

cost = 0.0015
ob_tick_n = 30 # 觀察過去幾個tick
max_spread = 2 # bid1 ask1 差幾個tick
hit_bid_n = 20 # hit bid次數 (hit bid次數夠多)
hit_bid_vr = 0.8 # hit bid vol要大於avgbidv1的幾倍 (hit bid vol要夠多)
bidv21r = 0.4 # bidv2小於avgbidv1的幾倍 (bidv2沒有太厚)
hv_avgbidv1 = 0.4 # 掛單量小於avgbidv1的幾倍
hv_bidv1 = 0.8 # 掛單小於bidv1的幾倍
hit_entry_r = 1.4