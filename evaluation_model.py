import matplotlib.pyplot as plt
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
import pickle as pk
from scipy.spatial.distance import euclidean
from fastdtw import fastdtw

PRE_NAME = "onemin_ohlc_"
BEGIN_TIME = "09:00:00"
END_TIME = "11:00:00"
NUM_CLUSTER = 50
TIME_STEP = 5

import matplotlib.pyplot as plt
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
import pickle
from scipy.spatial.distance import euclidean
from fastdtw import fastdtw
PRE_NAME = "onemin_ohlc_"
BEGIN_TIME = "09:00:00"
END_TIME = "10:30:00"
NUM_CLUSTER = 50
TIME_STEP = 10

def load_data(date_begin='20180612', date_end = '20200301', split_date_begin = '20200302', split_date_end = '20200915', train = True):
    X = []
    Y = []

    
    for sid in tqdm(os.listdir(os.path.join('dataset'))):
        for file in os.listdir(os.path.join('dataset', sid)):
            curday = file[12:20]
            if (train == True and curday <= date_end and curday >= date_begin) or (train == False and curday >= split_date_begin and curday <= split_date_end):
                df = pd.read_csv(os.path.join('dataset', sid, file))
                df = df
                mask = (df.loc[:, "time"] >= BEGIN_TIME) & (df.loc[:, "time"] <= END_TIME)
                front_df = df[mask].loc[:, "return"]
                front_df = front_df.take(np.arange(0, len(front_df), TIME_STEP))
                end_df = df[~mask].loc[:, "return"]
                if len(front_df) == (91 // TIME_STEP +1):
                    X.append(np.array(front_df))
                    Y.append(np.array(end_df))
    return np.array(X), np.array(Y)

def dtw_d(X, Y):
    manhattan_distance = lambda x, y: np.abs(x - y)
    d, cost_matrix, acc_cost_matrix, path = dtw(X, Y, dist=manhattan_distance)
    return d

def dtw_affinity(X):
    return pairwise_distances(X, metric=dtw_d)

def fastdtw_d(X, Y):
    return fastdtw(X, Y, dist=euclidean)[0]

def fastdtw_affinity(X):
    return pairwise_distances(X, metric=fastdtw_d)


X, Y = load_data()

def dtw_d(X, Y):
    manhattan_distance = lambda x, y: np.abs(x - y)
    d, cost_matrix, acc_cost_matrix, path = dtw(X, Y, dist=manhattan_distance)
    return d

def dtw_affinity(X):
    return pairwise_distances(X, metric=dtw_d)

def fastdtw_d(X, Y):
    manhattan_distance = lambda x, y: np.abs(x - y)
    return fastdtw(X, Y, dist=manhattan_distance)[0]

def fastdtw_affinity(X):
    return pairwise_distances(X, metric=fastdtw_d)


def make_long_simple(y, cost):
    return y.max() - y[0] - cost
def make_short_simple(y, cost):
    return y[0] - y.min() - cost
def make_long_max_lost(y, cost):
    return y.min() - y[0] - cost
def make_short_max_lost(y, cost):
    return y[0] - y.max() - cost
def make_long(y, cost, exp_profit):
    if (y-y[0]-cost >= exp_profit).any():
        return exp_profit
    else:
        return y[-1] - y[0] - cost

def make_short(y, cost, exp_profit):
    if (y[0]-y-cost >= exp_profit).any():
        return exp_profit
    else:
        return -y[-1] + y[0] - cost
    

def find_cluster(X, X_table):
    prev_min = fastdtw_d(X, X_table[0])
    prev_min_arg = 0
    for i in range(1, NUM_CLUSTER):
        cur_min = fastdtw_d(X, X_table[i])
        if  cur_min <= prev_min:
            prev_min = cur_min
            prev_min_arg = i
    return prev_min_arg
def evaluate(X_test, Y_test, X_table, exp_profit=0.025):
    profit_long_array = np.zeros(NUM_CLUSTER)
    profit_short_array = np.zeros(NUM_CLUSTER)
    lost_long_array = np.zeros(NUM_CLUSTER)
    lost_short_array = np.zeros(NUM_CLUSTER)
    num_exchange_array = np.zeros(NUM_CLUSTER).astype("int")
    X_label = np.zeros(NUM_CLUSTER).astype("int")
    for i in tqdm(range(len(X_test))):
        X_label = find_cluster(X_test[i], X_table)
        # profit_long_array[X_label] += make_long(Y_test[i], 0.002, exp_profit)
        profit_short_array[X_label] += make_short(Y_test[i], 0.002, exp_profit)
        num_exchange_array[X_label] += 1
        
        
    # print('avg long return',sorted(profit_long_array/num_exchange_array)[::-1][:10])
    # print('avg short return' ,sorted(profit_short_array/num_exchange_array)[::-1][:10])
    # print(num_exchange_array)
    return profit_long_array, profit_short_array, num_exchange_array 


def load_pk_data(filename):
    pass
if __name__ == "__main__":
    # X, Y = load_data()
    # X_test, Y_test = load_data(train=False)
    # pk.dump(X, open(os.path.join('dataset', 'X.pk'), 'wb'))
    # pk.dump(Y, open(os.path.join('dataset', 'Y.pk'), 'wb'))
    # pk.dump(X_test, open(os.path.join('dataset_pk', 'X_test.pk'), 'wb'))
    # pk.dump(Y_test, open(os.path.join('dataset_pk', 'Y_test.pk'), 'wb'))
    
    X_test = pk.load(open(os.path.join('dataset_pk', 'X_test.pk'), 'rb'))
    Y_test = pk.load(open(os.path.join('dataset_pk', 'Y_test.pk'), 'rb'))
    X_table = pk.load(open(os.path.join('dataset_pk', 'X_table.pk'), 'rb'))
    print(X_test.shape)
    print(Y_test.shape)
    best_long_cluster = np.array([44, 33, 14, 21, 37,  2, 38,  4,  8, 12, 29, 24, 18, 48, 40,  7, 34,
       28, 36, 20, 16, 41,  0, 11, 46, 25, 31,  6, 13, 47, 42, 30,  5, 35,
       45, 23,  1, 10, 32, 15, 49,  9, 19, 26, 17, 39, 43, 22,  3, 27])
    best_short_cluster = np.array([ 3, 43, 17, 45, 23,  9, 19, 22, 26,  1, 49, 32, 35, 47, 15,  5, 39,
       13, 31, 46, 25, 34, 10, 41, 27, 20,  7, 36, 42, 11, 30,  0, 16, 28,
       18, 48, 12,  6, 24,  8,  4,  2, 29, 38, 37, 14, 40, 33, 21, 44])

    profit_long_array, profit_short_array, num_exchange_array  = evaluate(X_test, Y_test, X_table, 0.035)

    # print(profit_long_array)
    # print(profit_short_array)
    # print(num_exchange_array)
    for j in range(10):
        i = best_short_cluster[j]
        if num_exchange_array[i]:
            print(i, profit_short_array[i], num_exchange_array[i], profit_short_array[i]/num_exchange_array[i])

    profit_long_array, profit_short_array, num_exchange_array  = evaluate(X_test, Y_test, X_table, 0.04)

    # print(profit_long_array)
    # print(profit_short_array)
    # print(num_exchange_array)
    for j in range(10):
        i = best_short_cluster[j]
        if num_exchange_array[i]:
            print(i, profit_short_array[i], num_exchange_array[i], profit_short_array[i]/num_exchange_array[i])


    profit_long_array, profit_short_array, num_exchange_array  = evaluate(X_test, Y_test, X_table, 0.045)

    # print(profit_long_array)
    # print(profit_short_array)
    # print(num_exchange_array)
    for j in range(10):
        i = best_short_cluster[j]
        if num_exchange_array[i]:
            print(i, profit_short_array[i], num_exchange_array[i], profit_short_array[i]/num_exchange_array[i])