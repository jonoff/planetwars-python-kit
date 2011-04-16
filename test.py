'''r= {}
for ranking in range(10):
    for i in range(3):
        r[ranking] = r.get(ranking, [])
        r[ranking].append(i)
        
print r'''

class C:
    a=5
    def __repr__(self):
        return "RPR"
    def p(self):
        print self
    
a = C()
b = C()
c = C()

a.p()
b.p()

lst = [a,b,c]

'''for i in lst:
    if i == lst[-1]:
        print "LAST", i'''
        
#d = {'b':[a,b,c], 'c':[b,c]}
d = [['b', [a,b,c]], ['c', [b,c]]]
print d[0], '\n'
print d[0][1], '\n'
print d[1][1][1].a

#print [x[1] for x in d]
for a in d:
    for b in a[1]:
            print b.a
print '\n=', sum([sum([x.a for x in z[1]]) for z in d])
#print [sum([x.a for x in x]) for x in d]
#print sum([sum([x.a for x in x]) for x in d])