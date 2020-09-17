import pandas as pd
import numpy as np
import time
import datetime as dt
import os
from tqdm import tqdm
from sklearn.cluster import KMeans
from sklearn.cluster import AgglomerativeClustering
from dtw import dtw
from sklearn.metrics import pairwise_distances
PRE_NAME = "onemin_ohlc_"
BEGIN_TIME = "09:00:00"
END_TIME = "11:00:00"
def load_data():
    X = []
    Y = []
    # df = pd.read_csv(os.path.join('dataset', '2327', PRE_NAME+"20180612.csv"))
    # mask = (df.loc[:, "time"] >= BEGIN_TIME) & (df.loc[:, "time"] <= END_TIME)
    # front_df = df[mask].loc[:, "return"]
    # end_df = df[~mask].loc[:, "return"]
    # X.append(np.array(front_df))
    # Y.append(np.array(end_df))
    # """我是分隔線^^~"""
    # df = pd.read_csv(os.path.join('dataset', '2327', PRE_NAME+"20180613.csv"))
    # mask = (df.loc[:, "time"] >= BEGIN_TIME) & (df.loc[:, "time"] <= END_TIME)
    # front_df = df[mask].loc[:, "return"]
    # end_df = df[~mask].loc[:, "return"]
    # X.append(np.array(front_df))
    # Y.append(np.array(end_df))
    
    
    sid = '2327'
    for file in os.listdir(os.path.join('dataset', sid)):
        # print(file)
        df = pd.read_csv(os.path.join('dataset', sid, file))
        mask = (df.loc[:, "time"] >= BEGIN_TIME) & (df.loc[:, "time"] <= END_TIME)
        front_df = df[mask].loc[:, "return"]
        # print(front_df)
        # exit()
        end_df = df[~mask].loc[:, "return"]
        if len(front_df) == 121:
        #     print(df.to_string())
        #     exit()
        # print(np.array(front_df).shape)
            X.append(np.array(front_df))
            Y.append(np.array(end_df))
    # print(end_df)
    # df = pd.read_csv(os.path.join('dataset', '2327', PRE_NAME+"20180612.csv"))
    # print(len(X))
    # print(len(X[0]))
    # X = np.array(X)
    # print(X.shape)
        
    # exit()
    return np.array(X), np.array(Y)

def dtw_d(X, Y):
    manhattan_distance = lambda x, y: np.abs(x - y)
    d, cost_matrix, acc_cost_matrix, path = dtw(X, Y, dist=manhattan_distance)
    return d

def dtw_affinity(X):
    return pairwise_distances(X, metric=dtw_d)

if __name__ == "__main__":
    X, Y = load_data()
    # print(X.shape)
    # print(X.shape)
    # print(np.array)
    # print(dtw_d(X[0], X[1]))
    # exit()
    # print(d)
    ac = AgglomerativeClustering(n_clusters = 10,
                                 affinity = dtw_affinity,
                                 linkage = 'complete')
    X_label = ac.fit_predict(X)
    print(X_label)
    print(X.shape)