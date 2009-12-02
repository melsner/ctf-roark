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

ec05 = [
    {
    "ROOT_0":["ROOT_0"],
    "P":["HP", "MP"],
    },
    {
    "ROOT_0":["ROOT_0"],
    "HP":["S_", "N_"],
    "MP":["A_", "P_"],
    },
    {
    "ROOT_0":["ROOT_0"],
    "S_":["S_0", "VP_0", "UCP_0", "SQ_0", "SBAR_0", "SBARQ_0", "SINV_0"],
    "N_":["NP_0", "NAC_0", "NX_0", "LST_0", "X_0", "UCP_0", "FRAG_0"],
    "A_":["ADJP_0", "QP_0", "CONJP_0", "ADVP_0", "INTJ_0", "PRN_0"],
    "P_":["PP_0", "PRT_0", "RRC_0", "WHADJP_0", "WHADVP_0",
          "WHNP_0", "WHPP_0"],
    },
    ]

def leftCorner(tree):
    if type(tree[1]) is not tuple:
        return (tree[0].split("_")[0], tree[1])
    return leftCorner(tree[1])

class ValidationEvents:
    def __init__(self):
        self.events = DefaultDict(DefaultDict(0))

    def record(self, tree):
       if type(tree[1]) is not tuple:
            #terminal
            pass
       else:
           lhs = tree[0]
           (leftPos, leftWord) = leftCorner(tree)
           self.events[lhs][(leftPos, leftWord)] += 1

           for child in tree[1:]:
               self.record(child)

class GrammarStats:
    def __init__(self):
        self.ruleCounts = DefaultDict(DefaultDict(0))
        self.ruleTotals = DefaultDict(0)
        self.termCounts = DefaultDict(DefaultDict(0))
        self.termTotals = DefaultDict(0)
        self.ntToWord = DefaultDict(DefaultDict(0))
        self.ntToPos = DefaultDict(DefaultDict(0))
        self.ntToWordTot = DefaultDict(0)
        self.ntToPosTot = DefaultDict(0)

        self.lambdas = {}

    def addToGrammar(self, grammar, level):
        for pos in self.termCounts:
            #pos tags are not merged by this ctf
#            print pos
            grammar.addAncestry(level, pos, pos)

        for lhs,subtab in self.ruleCounts.items():
            for rhs, prob in subtab.items():
                rule = HierRule(level)
                if rhs[0] == "EPSILON":
                    rhs = []
                rule.setup(lhs, rhs, prob)

                if rule.epsilon():
                    grammar.addEpsilonRule(rule)
                else:
                    grammar.addRule(rule)

        for lhs, subtab in self.termCounts.items():
            for word, prob in subtab.items():
                rule = HierRule(level)
                rule.setup(lhs, [word,], prob)
                grammar.addTerminalRule(rule)

        for lhs, subtab in self.ntToWord.items():
            for word, prob in subtab.items():
                grammar.addWordLookahead(lhs, word, prob, level)

        for lhs, subtab in self.ntToPos.items():
            self.ntToPos[lhs] = dict(subtab)
        grammar.addNTToPos(self.ntToPos, level)
        grammar.addLambdas(self.lambdas, level)

    def record(self, tree):
        if type(tree[1]) is not tuple:
            #terminal
            lhs = tree[0]
            word = tree[1]
            self.termCounts[lhs][word] += 1
            self.termTotals[lhs] += 1
        else:
            lhs = tree[0]
            rhs = tuple([st[0] for st in tree[1:]])
            self.ruleCounts[lhs][rhs] += 1
            self.ruleTotals[lhs] += 1

            (leftPos, leftWord) = leftCorner(tree)

            self.ntToWord[lhs][leftWord] += 1
            self.ntToPos[lhs][leftPos] += 1
            self.ntToWordTot[lhs] += 1
            self.ntToPosTot[lhs] += 1

            for child in tree[1:]:
                self.record(child)

    def normalize(self):
        for lhs,tot in self.ruleTotals.items():
            subtab = self.ruleCounts[lhs]
            for rhs in subtab:
                subtab[rhs] /= tot

        for lhs,tot in self.termTotals.items():
            subtab = self.termCounts[lhs]
            for rhs in subtab:
                subtab[rhs] /= tot

        for lhs,tot in self.ntToWordTot.items():
            subtab = self.ntToWord[lhs]
            for rhs in subtab:
                subtab[rhs] /= tot

        for lhs,tot in self.ntToPosTot.items():
            subtab = self.ntToPos[lhs]
            for rhs in subtab:
                subtab[rhs] /= tot

    def learnLambdas(self, validation):
        (ll, wordRight,norm) = self.estep(validation)

        for step in range(10):
            print "LL", ll

            for lhs,tot in norm.items():
                lamb = wordRight[lhs]/tot
                if lamb < 1e-5:
                    lamb = 1e-5
                if lamb > 1 - 1e-5:
                    lamb = 1 - 1e-5

                self.lambdas[lhs] = lamb

            (ll, wordRight,norm) = self.estep(validation)            

    def estep(self, validation):
        ll = 0
        wordRight = DefaultDict(0)
        norm = DefaultDict(0)

        for lhs,subtab in validation.events.items():
            for (pos, word),ct in subtab.items():
                try:
                    pGivenWord = self.ntToWord[lhs][word]
                except KeyError:
                    pGivenWord = 0
                try:
                    pGivenPOS = self.ntToPos[lhs][pos] * \
                                self.termCounts[pos][word]
                except KeyError:
                    pGivenPOS = 0
                total = pGivenWord + pGivenPOS
                if total == 0:
#                    print "WARNING, zero-prob event", lhs, word, pos, ct
                    continue
                wordRight[lhs] += (pGivenWord / total) * ct
                norm[lhs] += total * ct

                ll += log(total) * ct

        return ll, wordRight, norm

if __name__ == "__main__":
    (grammarStem, out, trees, validation) = sys.argv[1:]

    print "Grammar stem:", grammarStem, "Output:", out, "Training:", trees,\
          "Validation:", validation

    grammar = HierGrammar(out, mode='w')

    topLevel = len(ec05) - 1

    for level,mapping in reversed(list(enumerate(ec05))):
#        print level, mapping
        for anc,children in mapping.items():
            for child in children:
                grammar.addAncestry(level + 1, anc, child)
                grammar.addAncestry(level + 1, "@%s" % anc, "@%s" % child)

#    print grammar.hierarchy

    grammar.makeMapping(topLevel)

#    print grammar.pennToLevel

    for level in range(len(ec05)):
        gstats = GrammarStats()
        vstats = ValidationEvents()

        for ct,line in enumerate(file(trees)):
            if ct % 100 == 0:
                print "read trees", ct
            tree = grammar.transform(level + 1, zeroSplit(
                binarizeTree(
                treeToTuple(line.strip()))))

#            print treeToStr(tree)
            gstats.record(tree)

        for ct,line in enumerate(file(validation)):
            if ct % 1000 == 0:
                print "read validation trees", ct
            tree = grammar.transform(level + 1, zeroSplit(
                binarizeTree(
                treeToTuple(line.strip()))))
            vstats.record(tree)

        gstats.normalize()
        gstats.learnLambdas(vstats)

        print gstats.lambdas
#        print gstats.ntToWord

        gstats.addToGrammar(grammar, level)

    for pos in gstats.termCounts:
        #pos tags are not merged by this ctf
#        print pos
        grammar.addAncestry(topLevel + 1, pos, pos)

    #begin copied code
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
        level += topLevel + 1
        assert(arrow == "->")
        grammar.addAncestry(level, parNT, childNT)

    grammar.writeback("hierarchy")

    for realLevel in range(maxLevel+1):
        print >>sys.stderr, "Level", realLevel

        grammarFile = workDir/("%s-txt-lvl%d.grammar" % (basename, realLevel))
        level = realLevel + topLevel + 1

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

    for realLevel in range(maxLevel+1):
        print >>sys.stderr, "Level", realLevel

        lexicon = workDir/("%s-txt-lvl%d.lexicon" % (basename, realLevel))
        level = realLevel + topLevel + 1

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

    for realLevel in range(maxLevel+1):
        print >>sys.stderr, "RealLevel", realLevel

        lookahead = workDir/("%s-txt-lvl%d.lookahead.gz" %
                             (basename, realLevel))

        level = realLevel + topLevel + 1

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

        if realLevel == 0:
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
