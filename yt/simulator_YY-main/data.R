packages <- c('glue', 'tidyverse', 'data.table', 'zoo', 'lubridate')
invisible(lapply(packages, function(x) suppressPackageStartupMessages(require(x, character.only=T))))

dlist <- fread('E:/data/tradingdate_data.csv')
dlist <- sort(as.character(dlist$date))

setwd("F:/algo/simulator_python")

for(i in c(575:length(dlist))){
    
    td <- dlist[i]
    tdst <- as.character(as.Date(td, format="%Y%m%d"))
    if(file.exists(glue('{td}_adj.csv'))){next}
    print(td)

    # otc 及 twse 之 seq 會重複，故把 otc 之 seq 都加上0.1
    slob <- rbind(fread(glue("D:/data/raw_data/{tdst}/tse_lob.csv")),
                  fread(glue("D:/data/raw_data/{tdst}/otc_lob.csv")) %>% mutate(V2=V2+0.1))
    colnames(slob) <- c("txtime", "seq", "sid",
                        paste0(c("bid", "bidv"), rep(1:5, each=2)), "bidx",
                        paste0(c("ask", "askv"), rep(1:5, each=2)), "askx")
    slob <- slob %>% 
        filter(nchar(sid)==4) %>%
        filter(txtime>=85500000) %>%
        select(-askx, -bidx)
    
    stick <- rbind(fread(glue("D:/data/raw_data/{tdst}/tse_tick.csv")),
                   fread(glue("D:/data/raw_data/{tdst}/otc_tick.csv")) %>% mutate(V2=V2+0.1))
    colnames(stick) <- c("txtime", "seq", "sid", "txtimer",
                         "tick", "volume", "cumvolumes1", "k1", "k2", "codec")
    stick <- stick %>% 
        filter(tick!=0 & volume!=0) %>%
        filter(nchar(sid)==4) %>%
        filter(txtime>=85500000) %>%
        select(seq, txtime, sid, tick, volume, codec)
    
    df <- slob %>% 
        full_join(stick, by=c('txtime', 'sid', 'seq')) %>%
        group_by(sid) %>%
        arrange(seq) %>%
        mutate(codec=na.locf(codec, na.rm=F)) %>% # 幫lob填上codec
        ungroup() %>%
        mutate(codec=replace_na(codec, 128)) %>% # 還是沒有者填 128
        # 強制盤中 lob codec 為 16 (最後開盤時間09:02後依然沒有成交者)
        mutate(codec=ifelse(is.na(tick) & codec==128 & 
                            txtime>=90300000 & txtime<=132500000, 16, codec)) %>%
        arrange(txtime, seq) %>%
        mutate(seq=c(1:n())) %>%
        mutate_all(replace_na, replace=0)
    
    fwrite(df, glue('{td}.csv'))  
    
        
    adj_slob <- slob %>% 
        mutate(tg=1000*round(txtime/1000)) %>%
        group_by(sid, tg, bid1, ask1) %>%
        top_n(1, seq) %>%
        ungroup() %>%
        select(-tg)
    
    adj_stick <- stick %>%
        mutate(tg=1000*round(txtime/1000)) %>%
        group_by(sid, tg, tick, codec) %>%
        summarise(seq=max(seq),
                  txtime=max(txtime),
                  volume=sum(volume)) %>%
        ungroup() %>%
        select(seq, txtime, sid, tick, volume, codec)
    
    adj_df <- adj_slob %>% 
        full_join(adj_stick, by=c('txtime', 'sid', 'seq')) %>%
        group_by(sid) %>%
        arrange(seq) %>%
        mutate(codec=na.locf(codec, na.rm=F)) %>% # 幫lob填上codec
        ungroup() %>%
        mutate(codec=replace_na(codec, 128)) %>% # 還是沒有者填 128
        # 強制盤中 lob codec 為 16 (最後開盤時間09:02後依然沒有成交者)
        mutate(codec=ifelse(is.na(tick) & codec==128 & 
                                txtime>=90300000 & txtime<=132500000, 16, codec)) %>%
        arrange(txtime, seq) %>%
        mutate(seq=c(1:n())) %>%
        mutate_all(replace_na, replace=0) 

    fwrite(adj_df, glue('{td}_adj.csv'))
}