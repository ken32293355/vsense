# simulator_python

### 資料
* 資料位於 https://drive.google.com/drive/folders/1Q8a9Q7tieC3fqbVFIIaZkH8a9gstAr2G?usp=sharing
* 有adj尾綴者為調整過後的資料，可以節省時間。無尾綴者為實際交易資料。

### 使用方法
```python
if __name__ == "__main__":
    st = sibs('sibs', '', 0, 0, '1', True, 'sim')
    sim = simulator(st, '20201104_adj.csv', 150)
    sim.start()
```

### 注意事項
1. 策略需繼承base_strategy
2. router jasper 由base_strategy連接
3. 註冊tick跟lob需使用 base_strategy 之 reg_lob() 及 reg_tick()
4. 與時間相關之操作需寫於 time_dependent_event() 中
5. 註冊的股票檔數越多，資料筆數越多，跑得越慢。
6. 目前只有股票功能(不含權證、期貨)"# simulator_YY" 
# simulator_YY
