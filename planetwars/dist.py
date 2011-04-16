#!/usr/bin/python
from math import ceil, sqrt
e=(21.962964, 22.23102) #1 36 5
m=(4.851626, 24.772172) #2 340 1
n=(11.97462, 28.515376) #0 58 5

dx = m[0] - e[0]
dy = m[1] - e[1]
me_to_e = int(ceil(sqrt(dx ** 2 + dy ** 2)))

dx = m[0] - n[0]
dy = m[1] - n[1]
me_to_n = int(ceil(sqrt(dx ** 2 + dy ** 2)))

dx = n[0] - e[0]
dy = n[1] - e[1]
n_to_e = int(ceil(sqrt(dx ** 2 + dy ** 2)))

print "me_to_e%s me_to_n%s n_to_e%s" % (me_to_e, me_to_n, n_to_e)
print  (me_to_n + n_to_e) - me_to_e
