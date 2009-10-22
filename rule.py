from __future__ import division

class Rule:
    def setup(self, lhs, rhs, prob):
        self.lhs = lhs
        assert(0 <= len(rhs) <= 2)
        self.rhs = rhs
        self.prob = prob

    def __init__(self, string=None):
        if string == None:
            return

        fields = string.strip().split()

        if not (2 < len(fields) < 6):
            raise ValueError("Bad rule format: %s" % string)

        (prob, lhs, arrow) = fields[0:3]
        rhs = []
        if len(fields) > 3:
            rhs.append(fields[3])
            if len(fields) > 4:
                rhs.append(fields[4])

        assert arrow == "->", ("Bad rule format: %s" % string)

        self.lhs = lhs
        self.rhs = rhs
        self.prob = float(prob)

    def __cmp__(self, other):
        try:
            return cmp(self.lhs, other.lhs) or cmp(self.rhs, other.rhs)
        except AttributeError:
            return 1

    def epsilon(self):
        return not self.rhs

    def unary(self):
        return len(self.rhs) == 1

    def unaryMatch(self, word):
        return self.unary() and word == self.rhs[0]

    def __repr__(self):
        return "%g %s -> %s" % (self.prob, self.lhs, " ".join(self.rhs))
