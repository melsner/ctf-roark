from __future__ import division
import sys
import cPickle as pickle
from gzip import GzipFile
import re
from math import log, exp

from AIMA import DefaultDict

from HierGrammar import HierGrammar, HierRule
from convertLCGrammarToHier import readLambdas, readProductionTable, listEval

from path import path

from treeUtils import binarizeTree, treeToTuple, treeToStr, zeroSplit

if __name__ == "__main__":
    (grammarStem, out, realLevel) = sys.argv[1:]
    realLevel = int(realLevel)

    print "Grammar stem:", grammarStem, "Output:", out, "Level:", realLevel

    grammar = HierGrammar(out, mode='w')

    grammarStem = path(grammarStem).abspath()
    workDir = grammarStem.dirname()
    basename = grammarStem.basename()

    hierFile = workDir/("%s-txt.hier" % (basename,))
    for line in file(hierFile):
        fields = line.strip().split()
        (level, parNT, arrow, childNT) = fields
        level = int(level)
        assert(arrow == "->")
        grammar.addAncestry(level, parNT, childNT)

    grammar.writeback("hierarchy")

    grammarFile = workDir/("%s-txt-lvl%d.grammar" % (basename, realLevel))
    level = 0

    print >>sys.stderr, "Nonterms from", grammarFile

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

        rule = HierRule(level)

        if lhs.startswith("EPSILON"):
            assert(len(rhs) == 1)
            assert(rhs[0].startswith("EPSILON"))
            rhs = []
            #hack... epsilon always => epsilon
            prob = 1

        rule.setup(lhs, rhs, prob)

        if rule.epsilon() or rule.unary():
#                print >>sys.stderr, "Skipping bogus unary", rule
            pass
        else:
            grammar.addRule(rule)

    unaryFile = workDir/("%s-txt-lvl%d.unaries.gz" %
                         (basename, realLevel))

    print >>sys.stderr, "Unaries from", unaryFile

    ct = 0
    for line in GzipFile(unaryFile):
        if ct % 1000 == 0:
            print >>sys.stderr, ct, "..."
        ct += 1

        if not line.strip():
            continue

        #copied, factor
        fields = line.strip().split()
        (prob, lhs, arrow, rhs1) = fields
        assert(arrow == "->")

        rhs = [rhs1,]

        prob = float(prob)

        rule = HierRule(level)

        #there will be no rules directly inserting the terminal
        #epsilon in this file, because no terminal rules are in
        #this file...

        rule.setup(lhs, rhs, prob)

        if [rule.lhs,] == rule.rhs:
            print >>sys.stderr, "Warning: X->X", rule.lhs, rule.rhs
        elif not rule.unary():
            print >>sys.stderr, "WARNING: non-unary", rule
            assert(0)
        else:
            grammar.addRule(rule)

    grammar.writeback("grammar")

    lexicon = workDir/("%s-txt-lvl%d.lexicon" % (basename, realLevel))

    print >>sys.stderr, "Terminals from", lexicon

    ct = 0
    for line in file(lexicon):
        if ct % 1000 == 0:
            print >>sys.stderr, ct, "..."
        ct += 1

        fields = line.strip().split()
        (pos, word) = fields[0:2]
        lst = listEval(" ".join(fields[2:]))

        if word == "EPSILON":
            rhs = []
        else:
            rhs = [word,]

        for num,prob in enumerate(lst):
            preterm = "%s_%d" % (pos, num)
            rule = HierRule(level)
            rule.setup(preterm, rhs, float(prob))

            if [rule.lhs,] == rule.rhs:
                print >>sys.stderr, "Warning: X->X", rule.lhs, rule.rhs
            elif rule.epsilon():
                grammar.addEpsilonRule(rule)
            else:
                grammar.addTerminalRule(rule)

    grammar.writeback("terminals")
    grammar.writeback("epsilons")

    lookahead = workDir/("%s-txt-lvl%d.lookahead.gz" %
                         (basename, realLevel))

    print >>sys.stderr, "Lookahead data from", lookahead

    if lookahead.endswith(".gz"):
        look = GzipFile(lookahead)
    else:
        look = file(lookahead)

    lambdas = readLambdas(look)
    grammar.addLambdas(lambdas, level)
    ntToPos = readProductionTable(look)
    grammar.addNTToPos(ntToPos, level)

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
        grammar.addWordLookahead(nt, word, float(prob), level)

    #this table doesn't depend on level
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

    grammar.writeback("lookahead")
    grammar.writeback("ntToWord")
