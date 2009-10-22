from __future__ import division
import sys
import cPickle as pickle
from gzip import GzipFile

from AIMA import DefaultDict

from topdownParser import Grammar, Rule

def readLambdas(ff):
    lambdas = {}
    for line in ff:
        if not line.strip():
            return lambdas
        fields = line.strip().split()
        (nt, prob) = fields
        prob = float(prob)
        lambdas[nt] = prob
    return lambdas

def readProductionTable(ff):
    ntToWord = DefaultDict({})

    ct = 0
    for line in ff:
        if not line.strip():
            return ntToWord
        if ct % 1000 == 0:
            print >>sys.stderr, "read", ct, "..."
        ct += 1

        fields = line.strip().split()
        (prob, nt, arrow, word) = fields
        assert(arrow == "->")
        ntToWord[nt][word] = float(prob)
    return ntToWord

if __name__ == "__main__":
    (grammar, lexicon, lookahead, out) = sys.argv[1:]

    print "Grammar:", grammar, "Lexicon:", lexicon, "Lookahead:", lookahead

    rules = DefaultDict([])

    ct = 0
    for line in file(grammar):
        if ct % 1000 == 0:
            print >>sys.stderr, ct, "..."
        ct += 1
        
        fields = line.strip().split()
        (lhs, arrow, rhs1) = fields[0:3]
        assert(arrow == "->")
        if len(fields) == 5:
            rhs = [rhs1, fields[3]]
            prob = fields[4]
        elif len(fields) == 4:
            rhs = [rhs1,]
            prob = fields[3]

        prob = float(prob)

        rule = Rule()
        rule.setup(lhs, rhs, prob)

        if [rule.lhs,] == rule.rhs and rule.prob == 1.0:
            print >>sys.stderr, "Warning: X->X", rule.lhs, rule.rhs
        else:
            rules[rule.lhs].append(rule)

    ct = 0
    for line in file(lexicon):
        if ct % 1000 == 0:
            print >>sys.stderr, ct, "..."
        ct += 1
        
        fields = line.strip().split()
        (pos, word) = fields[0:2]
        lst = eval(" ".join(fields[2:]))

        for num,prob in enumerate(lst):
            preterm = "%s_%d" % (pos, num)
            rule = Rule()
            rule.setup(preterm, [word,], float(prob))

            if [rule.lhs,] == rule.rhs and rule.prob == 1.0:
                print >>sys.stderr, "Warning: X->X", rule.lhs, rule.rhs
            else:
                rules[rule.lhs].append(rule)

    grammar = Grammar(rules)

    if lookahead.endswith(".gz"):
        look = GzipFile(lookahead)
    else:
        look = file(lookahead)

    lambdas = readLambdas(look)
    ntToPos = readProductionTable(look)
    ntToWord = readProductionTable(look)
    posToWord = readProductionTable(look)

    grammar.setLookahead(lambdas, ntToPos, ntToWord, posToWord)

    print >>sys.stderr, "dumping"

    if out.endswith(".gz"):
        outfile = GzipFile(out, 'wb')
    else:
        outfile = file(out, 'wb')
    pickler = pickle.Pickler(outfile, protocol=-1)
    pickler.fast = 1
    pickler.dump(grammar)
        
