import pandas as pd
import numpy as np
import time
import datetime as dt
import os
from tqdm import tqdm

PRE_NAME = "onemin_ohlc_"
BEGIN_TIME = "09:00:00"
END_TIME = "11:00:00"
def load_data():
    X = None
    df = pd.read_csv(os.path.join('dataset', '2327', PRE_NAME+"20180612.csv"))
    mask = (df.loc[:, "time"] >= BEGIN_TIME) & (df.loc[:, "time"] <= END_TIME)
    front_df = df[mask].loc[:, "return"]
    end_df = df[~mask].loc[:, "return"]
    # print(df)
    print(front_df)
    print(end_df)
    # df = pd.read_csv(os.path.join('dataset', '2327', PRE_NAME+"20180612.csv"))
    return X

if __name__ == "__main__":
    load_data()