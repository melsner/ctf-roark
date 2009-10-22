import heapq

class X:
    def __init__(self, n):
        self.n = n
    def __cmp__(self, other):
        if self is other:
            return 0
        res = cmp(self.n, other.n)
        if res == 0:
            return cmp(id(self), id(other))
        return res
    def __hash__(self):
        return hash(id(self))
    def __repr__(self):
        return "X%d" % self.n

q = []
for num in [10, 4, 7, 8, 2, 1, 14, 10]:
    heapq.heappush(q, X(num))

for ct,it in enumerate(q):
    for ct2,it2 in enumerate(q):
        if ct != ct2:
            assert(it != it2)
        else:
            assert(it == it2)

di = {}
while q:
    x = heapq.heappop(q)
    print x
    di[x] = 1

print di
