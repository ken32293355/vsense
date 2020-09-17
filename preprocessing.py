import pandas as pd
import numpy as np
import time
import datetime as dt
import os
from tqdm import tqdm

def split_by_date(df):
    df.loc[:, 'date'] = df.loc[:, 'date'].astype(str)
    df.loc[:, 'sid'] = df.loc[:, 'sid'].astype(str)
    date_set = set(df.loc[:, 'date'])
    sid_set = set(df.loc[:, 'sid'])

    if not os.path.exists(os.path.join('dataset')):
        os.mkdir("dataset")


    for sid in sid_set:
        if not os.path.exists(os.path.join("dataset", sid)):
            os.mkdir(os.path.join("dataset", sid))

    df2 = None
    prev_date = df.loc[0, 'date']
    stock_df_dict = {}
    date_list = sorted(date_set)
    for i in tqdm(range(1, len(date_list))):
        pre_date = date_list[i-1]
        date = date_list[i]
        for sid in sid_set:
            mask = (df.loc[:, 'date'] == pre_date) & (df.loc[:, 'sid'] == sid)
            ref_price = float(df.loc[:, 'close'][mask].tail(1))
            mask = (df.loc[:, 'date'] == date) & (df.loc[:, 'sid'] == sid)
            df2 = df[mask]
            df2.loc[:, 'return'] = (df2.loc[:, "close"] - ref_price) / ref_price
            df2.to_csv(os.path.join("dataset", sid, "onemin_ohlc_" + date +".csv"), index = False)

            # exit()

if  __name__== "__main__":
    df = pd.read_csv("yclist_mk.csv").drop(["avg_price"], axis = 1)
    df = split_by_date(df)