from __future__ import division
import sys
import cPickle as pickle
from gzip import GzipFile
import re

from path import path
from AIMA import DefaultDict

from HierGrammar import HierGrammar, HierRule

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
    (grammarStem, out) = sys.argv[1:]

    print "Grammar stem:", grammarStem, "Output:", out

    grammar = HierGrammar(out, mode='w')

    grammarStem = path(grammarStem).abspath()
    workDir = grammarStem.dirname()
    basename = grammarStem.basename()

    fileLst = workDir.files(basename+"-txt-lvl*")
    fileNums = [re.search("-txt-lvl(\d+)", fileName) for fileName in fileLst]
    fileNums = [int(match.group(1)) for match in fileNums if match]
    maxLevel = max(fileNums)

    print "Max grammar level:", maxLevel

    hierFile = workDir/("%s-txt.hier" % (basename,))
    for line in file(hierFile):
        fields = line.strip().split()
        (level, parNT, arrow, childNT) = fields
        level = int(level)
        assert(arrow == "->")
        grammar.addAncestry(level, parNT, childNT)

    grammar.writeback("hierarchy")

    for level in range(maxLevel+1):
        print >>sys.stderr, "Level", level

        grammarFile = workDir/("%s-txt-lvl%d.grammar" % (basename, level))

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

            rule.setup(lhs, rhs, prob)

            if rule.epsilon() or rule.unary():
                print >>sys.stderr, "Skipping bogus unary", rule
            else:
                grammar.addRule(rule)

        unaryFile = workDir/("%s-txt-lvl%d.unaries.gz" % (basename, level))

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

            prob = float(prob)

            rule = HierRule(level)

            if lhs.startswith("EPSILON"):
                assert(len(rhs) == 1)
                assert(rhs[0].startswith("EPSILON"))
                rhs = []

            rule.setup(lhs, rhs, prob)

            if not (rule.epsilon() or rule.unary()):
                print >>sys.stderr, "WARNING: non-unary", rule
                assert(0)
            else:
                grammar.addRule(rule)

    grammar.writeback("grammar")

    for level in range(maxLevel+1):
        print >>sys.stderr, "Level", level

        lexicon = workDir/("%s-txt-lvl%d.lexicon" % (basename, level))

        print >>sys.stderr, "Terminals from", lexicon

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
                rule = HierRule(level)
                rule.setup(preterm, [word,], float(prob))

                if [rule.lhs,] == rule.rhs and rule.prob == 1.0:
                    print >>sys.stderr, "Warning: X->X", rule.lhs, rule.rhs
                else:
                    grammar.addTerminalRule(rule)

    grammar.writeback("terminals")

    for level in range(maxLevel+1):
        print >>sys.stderr, "Level", level

        lookahead = workDir/("%s-txt-lvl%d.lookahead.gz" %
                             (basename, level))

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

        if level == 0:
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
