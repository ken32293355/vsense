import pandas as pd
import numpy as np
import time
import datetime as dt
import os
from tqdm import tqdm

def split_by_date(df):
    # print(df)
    # sid_set = set(df.loc[:, "sid"])
    date_set = set(df.loc[:, "date"])
    # print(date_set)
    df2 = None
    for date in date_set:
        df2 = df.loc[:, date]
        print(df2)
        exit()
    return df

if  __name__== "__main__":
    df = pd.read_csv("yclist_mk.csv")
    df = split_by_date(df)