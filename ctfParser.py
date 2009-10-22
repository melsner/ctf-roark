from __future__ import division
import heapq
from AIMA import DefaultDict
import sys
from copy import deepcopy, copy
from math import log, exp

from Probably import assert_valid_prob

from topdownParser import Grammar, Rule, Parser, Analysis, \
     empty, normalizeTree, treeToStr, identityBeamF, cubicBeamF
from HierGrammar import HierGrammar, HierRule
from debugging import TargetParse, reportMatchingParses

class HierAnalysis(Analysis):
    def __init__(self, top="ROOT", initial=False):
        Analysis.__init__(self, top, initial)

        self.subLevelHeap = []
        self.usedFromPar = set()

        if initial > 1:
            self.subLevelHeap.append(
                HierAnalysis(top=top, initial=initial - 1))

    def level(self):
        if not self.deriv:
            assert(0), "Called lookahead on ROOT!"
        return self.deriv.level

    def subFOM(self, generalVersion, foremost):
        return (self.prob *
                foremost.derivationProbBackTo(generalVersion))

    def clone(self):
        ana = HierAnalysis()
        ana.parent = self

        ana.prob = self.prob
        ana.word = self.word
        return ana

    def derivationProbBackTo(self, prev):
        #improbably, memoizing this fn makes it *slower*
        if prev is self:
            return 1.0

        return self.deriv.prob * self.parent.derivationProbBackTo(prev)

    def derivationProbBackToWord(self, prevWord):
        if self.word == prevWord:
            return 1.0
        return self.deriv.prob * \
               self.parent.derivationProbBackToWord(prevWord)

    def howFarBack(self, prev):
        if prev is self:
            return 0
        return 1 + self.parent.howFarBack(prev)

    def firstUnused(self):
        if not self.parent:
            return
        for item in self.parent.subLevelHeap:
            if item not in self.usedFromPar:
                return item
        return None

#     def allUnused(self):
#         if not self.parent:
#             return
#         for item in self.parent.subLevelHeap:
#             if item not in self.usedFromPar:
#                 yield item

    def allUnused(self):
        #minimize use of iterators
        if not self.parent:
            return []
        res = []
        for item in self.parent.subLevelHeap:
            if item not in self.usedFromPar:
                res.append(item)
        return res

    def expansionProfile(self, foremost):
        heapPart = self.allUnused()
        myBit = (len(heapPart),
                 sum([x.subFOM(self, foremost) for x in heapPart]))

        if self.parent is None:
            return [myBit,]
        #rewrite if using a language with tail calls
        res = self.parent.expansionProfile(foremost)
        res.append(myBit)

        if self is foremost:
            myFinalBit = (len(self.subLevelHeap),
                          sum([x.subFOM(self, foremost)
                               for x in self.subLevelHeap]))

            res.append(myFinalBit)

        return res

    def nextStepToSpecify(self, foremost):
        #print >>sys.stderr, "should expand?", self, "in chain", id(foremost)

        #this node, if called upon, will expand analyses which have
        #one fewer derivation step than itself
        #these are stored at the parent
        #therefore this node should volunteer to expand something
        # if its parent's specific analyses are promising

        if self.parent is None:
            return (None, 0)

        toExpand = self.firstUnused()

        if toExpand:
            myFOM = toExpand.subFOM(self.parent, foremost)
        else:
            myFOM = 0

        (bestBeforeMe, bestFOM) = self.parent.nextStepToSpecify(foremost)

        if myFOM < bestFOM: #negative sign!
            #print >>sys.stderr, "I am best", myFOM
            return (self, myFOM)
        #print >>sys.stderr, "I am bad", bestFOM
        return (bestBeforeMe, bestFOM)

    def specifyNext(self, sentence, foremost, verbose=[]):
        nextRule = self.deriv

        toExpand = self.firstUnused()
        assert(toExpand)

        self.usedFromPar.add(toExpand)
        stackTop = toExpand.stackTop()

        if "subhyp" in verbose:
            print >>sys.stderr, "\texpanding", toExpand

        #parser.verbose.append("lookahead")

        for rule in nextRule.children:
            #the terminal attr is usually set by grammar.deriving
            #but we don't call that so we need to set it manually
            rule.terminal = nextRule.terminal

            if rule.lhs != stackTop:
                continue

            #print >>sys.stderr, "\t", rule

            #pass fakes to extend since we don't need a LAP
            newAna = toExpand.extend(rule,
                                     sentence[toExpand.word],
                                     None, #fake word
                                     None, #fake parser
                                     doFOM=False)
            #we'll compute the FOM on the fly every time we need it
            #but heapify based on prob
            newAna.fom = newAna.prob

            if "subhyp" in verbose:
                print >>sys.stderr, "\t", newAna

            heapq.heappush(self.subLevelHeap, newAna)

    def recalcProb(self):
        #could probably be speeded up with a knowledge of what changed
        self.recalcProbHelper(self)
        assert_valid_prob(-self.prob)
        self.fom = self.prob * self.lap

    def recalcProbHelper(self, foremost):
        res = sum([x.subFOM(self, foremost) for x in self.allUnused()])
        if self.parent:
            res + self.parent.recalcProbHelper(foremost)
        self.prob = res +\
                    sum([x.subFOM(self, foremost) for x in self.subLevelHeap])
        return res

class CTFParser(Parser):
    def __init__(self, grammar, top="ROOT", queueLimit=10000,
                 beamF=identityBeamF, mode=None, verbose=[],
                 makeAnalysis=HierAnalysis,
                 gammas=[1e-4,], deltas=[1e-3,],
                 stepExpansionLimit=500,
                 beamDivergenceFactor=10):
        Parser.__init__(self, grammar, top=top, queueLimit=queueLimit,
                        beamF=beamF, gamma=gammas[0], mode=mode,
                        verbose=verbose, makeAnalysis=makeAnalysis)
        #just for consistency... might have been set with a 'mode' flag
        #shouldn't matter though
        gammas[0] = self.gamma
        
        self.gammas = gammas
        self.deltas = deltas
        assert(len(self.deltas) == len(self.gammas) - 1)
        self.stepExpansionLimit = stepExpansionLimit
        self.beamDivergenceFactor = beamDivergenceFactor

    def afterGenerating(self, hyps, i, sentence):
        if not hyps[i + 1]:
            #fail?
            return

        for level,gamma in enumerate(self.gammas):
            if level == 0:

                if "level" in self.verbose:
                    print >>sys.stderr, "Specified", \
                          len(hyps[i + 1]), "hypotheses"
                    bestSub = hyps[i + 1][0]
                    print >>sys.stderr, "Best parse at level", level,\
                          treeToStr(bestSub.tree(allowPartial=True)),\
                          bestSub.prob
                    print >>sys.stderr, bestSub.expansionProfile(bestSub)

                continue

            if "level" in self.verbose:
                print >>sys.stderr, "Specifying at level", level

            self.specifyAtLevel(1, level, hyps[i + 1], 1.0, sentence)

            if "level" in self.verbose:
                gen = hyps[i + 1]

                try:
                    for subL in range(level):
                        gen = gen[0].subLevelHeap

                    bestSub = gen[0]
                    print >>sys.stderr, "Best parse at level", level,\
                          treeToStr(bestSub.tree(allowPartial=True)),\
                          bestSub.prob
                    print >>sys.stderr, bestSub.expansionProfile(bestSub)
                except:
                    print >>sys.stderr, \
                          "Warning: best hypothesis has no parse at level",\
                          level

                if self.verbose:
                    reportMatchingParses(self.verbose, hyps[i + 1], 0)
                    reportMatchingParses(self.verbose, hyps[i + 1], level)

        if "level" in self.verbose:
            bestSub = hyps[i + 1][0]
            print >>sys.stderr, "Best top-level parse",\
                  treeToStr(bestSub.tree(allowPartial=True)),\
                  bestSub.prob
            print >>sys.stderr, bestSub
            print >>sys.stderr, bestSub.expansionProfile(bestSub)

    def specifyAtLevel(self, level, targetLevel, hypsToProcess,
                       divergence, sentence):
        if not hypsToProcess:
            if "specify" in self.verbose:
                print >>sys.stderr, \
                      "WARNING: ordered to expand underspecified hypothesis"
            return 0

        processedHyps = []

        delta = self.deltas[level - 1] #level 0 has no delta
        gamma = self.gammas[level]

        nProcessed = 0

        while self.aboveGeneralThreshold(hypsToProcess,
                                         processedHyps, gamma):
            processing = heapq.heappop(hypsToProcess)
            prevProb = processing.prob
            if processedHyps and processedHyps[0].fom < 0:
                currentDiv = processing.fom / processedHyps[0].fom
            else:
                currentDiv = 1

            if "specify" in self.verbose:
                print >>sys.stderr, "specifying", processing

            if level < targetLevel:
                nProcessed += self.specifyAtLevel(
                    level + 1, targetLevel, processing.subLevelHeap,
                    divergence * currentDiv, sentence)
            else:
                nProcessed += 1
                self.specifyHyp(processing, delta, sentence,
                                divergence * currentDiv)

            processing.recalcProb()
            heapq.heappush(processedHyps, processing)

            if "specify" in self.verbose:
                print >>sys.stderr, "prob altered from", prevProb, "to",\
                      processing.prob

        if "level" in self.verbose and level == 1:
            print >>sys.stderr, "Specified", nProcessed, "hypotheses"

        for hyp in processedHyps:
            heapq.heappush(hypsToProcess, hyp)

        return nProcessed

    def aboveGeneralThreshold(self, hyps, completes, gamma):
        if not hyps:

            if "threshold" in self.verbose:
                print >>sys.stderr, "~~no more hypotheses"

            return False

        expandNext = hyps[0].fom
        nSpecified = len(completes)

        if nSpecified == 0:

            if "threshold" in self.verbose:
                print >>sys.stderr, "~~accept (no comparison)"

            return True

        bestOption = completes[0].fom
        nSpecified = 1 #XXX 
        beam = bestOption * self.beamF(gamma, nSpecified)

        if "threshold" in self.verbose:
            print >>sys.stderr, \
                  "~~merit %g, beam >= %g, fully specified %d" % (
                bestOption, beam, nSpecified)

        #- sign because minheap so everything is negative
        return expandNext <= beam

    def specifyHyp(self, hyp, delta, sentence, divergence):
        iters = 0
        step = self.aboveSpecificThreshold(hyp, delta, divergence)
        while step is not None:
            step.specifyNext(sentence, hyp, verbose=self.verbose)
            step = self.aboveSpecificThreshold(hyp, delta, divergence)
            iters += 1

            if iters > self.stepExpansionLimit:
                if "threshold" in self.verbose:
                    print >>sys.stderr, "==fail (too many iterations)"

                break

    def aboveSpecificThreshold(self, hyp, delta, divergence):
        (step, fom) = hyp.nextStepToSpecify(hyp)

        if not hyp.subLevelHeap:
            if "threshold" in self.verbose:
                print >>sys.stderr, "==accept (no comparison)"

            return step

        bestOption = hyp.subLevelHeap[0].subFOM(hyp, hyp)
        nSpecified = len(hyp.subLevelHeap)

        delta /= (divergence / self.beamDivergenceFactor)
        if delta > 1:
            delta = 1
        
        beam = bestOption * self.beamF(delta, nSpecified)        
        if "threshold" in self.verbose:
            print >>sys.stderr, \
                  "==merit %g, beam >= %g, fully specified %d" % (
                bestOption, beam, nSpecified)

        #- sign because minheap so everything is negative
        if fom <= beam:
            return step
        else:
            return None

if __name__ == "__main__":
    inf = sys.argv[1]

    print >>sys.stderr, "loading grammar", inf

    grammar = HierGrammar(inf)

    print >>sys.stderr, "done"

    debug = ["index", "pop", "push", "threshold",  "specify",
             "subhyp",]
#    tpar = TargetParse("[0.907997 ROOT_0 -> S_0, 0.238841 S_0 -> NP_0 @S_0, 0.0901318 NP_0 -> NP_0 @NP_0, 0.0371383 NP_0 -> NNP_0 NNP_0, 0.00284306 NNP_0 -> John, 0.000963901 NNP_0 -> Smith, 0.0432695 @NP_0 -> CC_0 NP_0, 0.885406 CC_0 -> and, 0.0371383 NP_0 -> NNP_0 NNP_0, 0.000232915 NNP_0 -> Mary, 8.14088e-05 NNP_0 -> Roe, 0.371818 @S_0 -> VP_0 ._0, 0.0129077 VP_0 -> VBP_0 NP_0, 0.487302 VBP_0 -> are, 0.0426093 NP_0 -> NNS_0, 0.000563345 NNS_0 -> friends, 0.999332 ._0 -> .]")

#     tpar1 = TargetParse("[0.907997 ROOT_0 -> S_0, 0.415826 S_0 -> NP_0 @S_1, 0.0244799 NP_0 -> NP_1 @NP_0, 0.0549577 NP_1 -> NNP_1 NNP_0, 0.00385792 NNP_1 -> John, 0.00185397 NNP_0 -> Smith, 0.0317599 @NP_0 -> CC_1 NP_1, 0.906293 CC_1 -> and, 0.0549577 NP_1 -> NNP_1 NNP_0, 0.000300947 NNP_1 -> Mary, 2.40844e-05 NNP_0 -> Roe, 0.515234 @S_1 -> VP_1 ._1, 0.00399242 VP_1 -> VBP_1 NP_0, 0.616828 VBP_1 -> are, 0.00149858 NP_0 -> NNS_0, 0.000944028 NNS_0 -> friends, 0.999461 ._1 -> .]", level=1)

#     tpar2 = TargetParse("[0.873076 ROOT_0 -> S_1, 0.508448 S_1 -> NP_0 @S_2, 0.0246014 NP_0 -> NP_3 @NP_0, 0.161513 NP_3 -> NNP_3 NNP_0, 0.00684764 NNP_3 -> John, 0.00333055 NNP_0 -> Smith, 0.0632427 @NP_0 -> CC_3 NP_2, 0.835953 CC_3 -> and, 0.0024399 NP_2 -> NNP_3 NNP_0, 0.000534297 NNP_3 -> Mary, 3.70439e-06 NNP_0 -> Roe, 0.79434 @S_2 -> VP_3 ._1, 0.00544183 VP_3 -> VBP_3 NP_1, 0.652744 VBP_3 -> are, 0.00117646 NP_1 -> NNS_1, 0.00152046 NNS_1 -> friends, 0.999461 ._1 -> .]", level=2)

    tpar = TargetParse("[0.907997 ROOT_0 -> S_0, 0.238841 S_0 -> NP_0 @S_0, 0.0164851 NP_0 -> DT_0 NNS_0, 0.0238421 DT_0 -> The, 0.00986581 NNS_0 -> stocks, 0.371818 @S_0 -> VP_0 ._0, 0.0177314 VP_0 -> VBD_0, 0.0149101 VBD_0 -> fell, 0.999332 ._0 -> .]", options=["expansions"])

    parser = CTFParser(grammar, top="ROOT_0", mode="lex",
                       queueLimit=5e5,
                       verbose=["index", "level", tpar],
                       makeAnalysis=HierAnalysis,
                       gammas=[1e-5, 1e-5],#, 1e-4, 1e-4],
                       deltas=[1e-4,],# 1e-4, 1e-3],
                       stepExpansionLimit=500)

    sent = "The stocks fell ."
#    sent = "John Smith and Mary Roe are friends ."

#     import cProfile
#     cProfile.run('parser.parse(sent.split())', 'profile-out-noiter')
#     sys.exit(0)

    final = parser.parse(sent.split())
    print final
    print list(final.derivation())
    print treeToStr(final.tree())
    print treeToStr(normalizeTree(final.tree()))
    print treeToStr(final.tree(True))

    level = 0
    while final.subLevelHeap:
        level += 1
        final = final.subLevelHeap[0]
        print
        print
        print "Level", level
        print final
        print list(final.derivation())
        print treeToStr(final.tree())
        print treeToStr(normalizeTree(final.tree(), stripSub=False))
        print treeToStr(final.tree(True))
