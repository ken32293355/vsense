import datetime as dt

BEGIN_TIME = "09:00:00"
END_TIME = "10:30:00"

h1, m1, s1 = [int(x) for x in BEGIN_TIME.split(":")]
h2, m2, s2 = [int(x) for x in END_TIME.split(":")]
t1 = dt.timedelta(hours = h1, minutes=m1)
t2 = dt.timedelta(hours = h2, minutes=m2)
print((t2-t1).total_seconds()//60)
# print(t2-t1, (t2-t1).minute)