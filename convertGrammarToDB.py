from __future__ import division
import sys
import cPickle as pickle
from gzip import GzipFile

from AIMA import DefaultDict

from topdownParser import Grammar, Rule
from DBGrammar import DBGrammar

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

def listEval(lst):
    undelimited = lst.lstrip("[").rstrip("]")
    items = undelimited.split(",")
    return items

if __name__ == "__main__":
    (grammarFile, lexicon, lookahead, out) = sys.argv[1:]

    print "Grammar:", grammarFile, "Lexicon:", lexicon, "Lookahead:", lookahead

    grammar = DBGrammar(out, mode='w')

    print >>sys.stderr, "Nonterms"

    ct = 0
    for line in file(grammarFile):
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
            grammar.addRule(rule)

    grammar.writeback("grammar")

    print >>sys.stderr, "Terminals"

    ct = 0
    for line in file(lexicon):
        if ct % 1000 == 0:
            print >>sys.stderr, ct, "..."
        ct += 1
        
        fields = line.strip().split()
        (pos, word) = fields[0:2]
        lst = listEval(" ".join(fields[2:]))

        for num,prob in enumerate(lst):
            preterm = "%s_%d" % (pos, num)
            rule = Rule()
            rule.setup(preterm, [word,], float(prob))

            if [rule.lhs,] == rule.rhs and rule.prob == 1.0:
                print >>sys.stderr, "Warning: X->X", rule.lhs, rule.rhs
            else:
                grammar.addTerminalRule(rule)

    grammar.writeback("terminals")

    print >>sys.stderr, "Lookahead"

    if lookahead.endswith(".gz"):
        look = GzipFile(lookahead)
    else:
        look = file(lookahead)

    lambdas = readLambdas(look)
    grammar.lambdas = lambdas
    ntToPos = readProductionTable(look)
    grammar.ntToPos = ntToPos

    grammar.writeback("lookahead")

    print >>sys.stderr, "Nonterm to word"

    ct = 0
    for line in look:
        if not line.strip():
            break
        if ct % 1000 == 0:
            print >>sys.stderr, "read", ct, "..."
        ct += 1

        fields = line.strip().split()
        (prob, nt, arrow, word) = fields
        assert(arrow == "->")
        grammar.addWordLookahead(nt, word, float(prob))

    grammar.writeback("ntToWord")

    print >>sys.stderr, "Pos to word"

    ct = 0
    for line in look:
        if not line.strip():
            break
        if ct % 1000 == 0:
            print >>sys.stderr, "read", ct, "..."
        ct += 1

        fields = line.strip().split()
        (prob, pos, arrow, word) = fields
        assert(arrow == "->")
        grammar.addPosToWord(pos, word, float(prob))

    grammar.writeback("posToWord")
