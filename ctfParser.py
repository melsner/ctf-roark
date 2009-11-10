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
                 sum([x.subFOM(self.parent, foremost) for x in heapPart]))

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

        if self is foremost:
            estimate = sum([x[1] for x in res])

#             if abs(estimate - foremost.prob) >= 1e-5:
#                 print res
#                 print "est", estimate, "record", foremost.prob
#                 foremost.recalcProb()
#                 print "newest value", foremost.prob
            
            assert(abs(estimate - foremost.prob) < 1e-5)

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
            print >>sys.stderr, "\texpanding", toExpand#, nextRule

        #parser.verbose.append("lookahead")

        for rule in nextRule.children:
            #the terminal attr is usually set by grammar.deriving
            #but we don't call that so we need to set it manually
            rule.terminal = nextRule.terminal

            if rule.lhs != stackTop:
                continue

            #not standard debug, comment out
            if "subhyp" in verbose:
                print >>sys.stderr, "\t", rule

            if toExpand.word >= len(sentence):
                #if we are done with the sentence, also fake this
                currWord = None
            else:
                currWord = sentence[toExpand.word]
            #pass fakes to extend since we don't need a LAP
            newAna = toExpand.extend(rule,
                                     currWord,
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
        if self.parent:
            res = sum([x.prob for x in self.allUnused()]) * self.deriv.prob
            res += self.parent.recalcProbHelper(foremost) * self.deriv.prob
        else:
            res = 0
        self.prob = res + sum([x.prob for x in self.subLevelHeap])
        return res

class CTFParser(Parser):
    def __init__(self, grammar, top="ROOT", queueLimit=10000,
                 beamF=identityBeamF, mode=None, verbose=[],
                 makeAnalysis=HierAnalysis,
                 gammas=[1e-4,], deltas=[1e-3,],
                 stepExpansionLimit=500,
                 beamDivergenceFactor=10,
                 subBeamF=identityBeamF):
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
        self.subBeamF = subBeamF

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

            self.specifyAtLevel(1, level, hyps[i + 1],
                                divergence=1.0, bestOption=None,
                                nOptions=0, sentence=sentence)

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
                       divergence, bestOption, nOptions, sentence):
        if not hypsToProcess:
            if "specify" in self.verbose:
                print >>sys.stderr, \
                      "WARNING: ordered to expand underspecified hypothesis"
            return (0, nOptions)

        processedHyps = []

        delta = self.deltas[level - 1] #level 0 has no delta
        gamma = self.gammas[targetLevel]

        nProcessed = 0

        if bestOption is None:
            assert(level == 1) #examining lvl 0 hyps
            bestOption = hypsToProcess[0].fom

        while self.aboveGeneralThreshold(hypsToProcess,
                                         processedHyps,
                                         bestOption=bestOption,
                                         nOptions=nOptions,
                                         gamma=gamma):
            processing = heapq.heappop(hypsToProcess)

            prevProb = processing.prob
            processing.recalcProb()

            if processing.prob > prevProb:
                if "specify" in self.verbose:
                    print >>sys.stderr, "prob reestimated from", \
                          prevProb, "to", processing.prob
                    print >>sys.stderr,\
                          processing.expansionProfile(processing)
                heapq.heappush(hypsToProcess, processing)
                continue

            prevProb = processing.prob
            if processedHyps and processedHyps[0].fom < 0:
                currentDiv = processing.fom / processedHyps[0].fom
            else:
                currentDiv = 1

            if "specify" in self.verbose:
                print >>sys.stderr, "specifying at", level, processing

            if level < targetLevel:
                (processed, currNOpt) = self.specifyAtLevel(
                    level + 1, targetLevel, processing.subLevelHeap,
                    divergence * currentDiv, bestOption, nOptions, sentence)
                nProcessed += processed
                nOptions = currNOpt
            else:
                nProcessed += 1
                #XX turn delta back on
                self.specifyHyp(processing, delta, bestOption, nOptions,
                                sentence, divergence * currentDiv)
                #XX previously used gamma only
#                 self.specifyHyp(processing, gamma, bestOption, nOptions,
#                                 sentence, divergence * currentDiv)
                nCreated = len(processing.subLevelHeap)
                nOptions += nCreated
                if nCreated == 0 and "specify" in self.verbose:
                    print >>sys.stderr, "WARNING: didn't reach the right edge"

#                 self.specifyHyp(processing, delta, sentence,
#                                 divergence * currentDiv)

            processing.recalcProb()
            heapq.heappush(processedHyps, processing)

            if "specify" in self.verbose:
                print >>sys.stderr, "prob altered from", prevProb, "to",\
                      processing.prob

        if "level" in self.verbose and level == 1:
            print >>sys.stderr, "Specified", nProcessed, "hypotheses"

        for hyp in processedHyps:
            heapq.heappush(hypsToProcess, hyp)

        return (nProcessed, nOptions)

    def aboveGeneralThreshold(self, hyps, completes, bestOption,
                              nOptions, gamma):
        if not hyps:

            if "threshold" in self.verbose:
                print >>sys.stderr, "~~no more hypotheses"

            return False

        expandNext = hyps[0].fom

        if expandNext == 0:

            if "threshold" in self.verbose:
                print >>sys.stderr, "~~reject (worthless hypothesis)"

            return False
        
        nSpecified = len(completes)

        if nSpecified == 0:

            if "threshold" in self.verbose:
                print >>sys.stderr, "~~accept (no comparison)"

            return True

        #bestOption = completes[0].fom
        ##self.beamF
        beam = bestOption * self.subBeamF(gamma, nOptions)

        if "threshold" in self.verbose:
            print >>sys.stderr, \
                  "~~merit %g, beam >= %g, fully specified %d" % (
                expandNext, beam, nSpecified)

        #- sign because minheap so everything is negative
        return expandNext <= beam

    def greedyToRightEdge(self, hyp, sentence):
        #start at the best point to expand
        (step, fom) = hyp.nextStepToSpecify(hyp)
        if step is None:
            #print >>sys.stderr, "greed finds nothing to do"
            return

        #print >>sys.stderr, "stepping", step.allUnused()
        #print >>sys.stderr, "hyp exp", hyp.expansionProfile(hyp)

        #keep going till we are at the step before the edge
        while step != hyp:
            #take a step
            step.specifyNext(sentence, hyp, verbose=self.verbose)

            #move forward to the child
            prevStep = step
            step = hyp

            #use stupid linear search to find the child
            while step.parent is not prevStep:
                step = step.parent
            #print >>sys.stderr, "stepped", step.allUnused()

            if not step.allUnused():
                #rules simply don't support this search path
                #print >>sys.stderr, "greed leads to nothing"
                return

        #and once more to get to the edge
        step.specifyNext(sentence, hyp, verbose=self.verbose)

    def specifyHyp(self, hyp, delta, bestOption, nOptions,
                   sentence, divergence):
        self.greedyToRightEdge(hyp, sentence)

        reachedRightEdge = bool(hyp.subLevelHeap)

        created = 0
        iters = 0
        step = self.aboveSpecificThreshold(hyp, delta, bestOption,
                                           nOptions, divergence)
        while step is not None:
            step.specifyNext(sentence, hyp, verbose=self.verbose)
            created = len(hyp.subLevelHeap)
            step = self.aboveSpecificThreshold(hyp, delta,
                                               bestOption, nOptions + created,
                                               divergence)
            iters += 1

            reachedRightEdge = reachedRightEdge or bool(hyp.subLevelHeap)
            #XXX hardcoded cutoff
            if not reachedRightEdge and iters > 20:
                if "threshold" in self.verbose:
                    print >>sys.stderr, "==fail (no visible progress)"

                break

            if iters > self.stepExpansionLimit:
                if "threshold" in self.verbose:
                    print >>sys.stderr, "==fail (too many iterations)"

                break

    def aboveSpecificThreshold(self, hyp, delta, bestOption, nOptions,
                               divergence):
        (step, fom) = hyp.nextStepToSpecify(hyp)

        if fom == 0:
            if "threshold" in self.verbose:
                print >>sys.stderr, "==reject (worthless hypothesis)"

            return None

        if not hyp.subLevelHeap:
            if "threshold" in self.verbose:
                print >>sys.stderr, "==accept (no comparison)"

            return step

        #bestOption = hyp.subLevelHeap[0].subFOM(hyp, hyp)
        #nSpecified = len(hyp.subLevelHeap)

#         delta /= (divergence / self.beamDivergenceFactor)
#         if delta > 1:
#             delta = 1
        
        beam = bestOption * self.beamF(delta, nOptions)        
        if "threshold" in self.verbose:
            print >>sys.stderr, \
                  "==merit %g, beam >= %g, fully specified %d" % (
                fom, beam, nOptions)

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

    tpar = TargetParse("""(ROOT_0 (RS_0 (NN_0 Food) (XXlcNN_0 (NNS_0 prices) (XXlcNP_0 (VP_0 (VBP_0 are) (XVlcVBP_0 (VP_0 (VBN_0 expected) (XVlcVBN_0 (S_0 (TO_0 to) (XSlcTO_0 (VP_0 (VB_0 be) (XVlcVB_0 (ADJP_0 (JJ_0 unchanged) (XPlcJJ_0 (XPlcADJP_0 (EPSILON_0 EPSILON)))) (XVlcVP_0 (EPSILON_0 EPSILON)))) (XSlcVP_0 (XSlcS_0 (EPSILON_0 EPSILON))))) (XVlcVP_0 (EPSILON_0 EPSILON)))) (XVlcVP_0 (EPSILON_0 EPSILON)))) (XXlcS_0 (,_0 ,) (@XXlcS_0 (CC_0 but) (@XXlcS_0 (S_0 (NN_0 energy) (XSlcNN_0 (NNS_0 costs) (XSlcNP_0 (VP_0 (VBD_0 jumped) (XVlcVBD_0 (NP_0 (RB_0 as) (XNlcRB_0 (JJ_0 much) (@XNlcRB_0 (IN_0 as) (@XNlcRB_0 (CD_0 4) (XNlcQP_0 (NN_0 %) (XNlcNP_0 (EPSILON_0 EPSILON))))))) (XVlcVP_0 (EPSILON_0 EPSILON)))) (XSlcS_0 (EPSILON_0 EPSILON))))) (XXlcS_0 (,_0 ,) (@XXlcS_0 (VP_0 (VBD_0 said) (XVlcVBD_0 (XVlcVP_0 (EPSILON_0 EPSILON)))) (@XXlcS_0 (NP_0 (NNP_0 Gary) (XNlcNNP_0 (NNP_0 Ciminero) (XNlcNP_0 (,_0 ,) (@XNlcNP_0 (NP_0 (NN_0 economist) (XNlcNN_0 (XNlcNP_0 (PP_0 (IN_0 at) (XPlcIN_0 (NP_0 (NNP_0 Fleet\/Norstar) (XNlcNNP_0 (NNP_0 Financial) (@XNlcNNP_0 (NNP_0 Group) (XNlcNP_0 (EPSILON_0 EPSILON))))) (XPlcPP_0 (EPSILON_0 EPSILON)))) (XNlcNP_0 (EPSILON_0 EPSILON))))) (XNlcNP_0 (EPSILON_0 EPSILON)))))) (@XXlcS_0 (._0 .) (XXlcSINV_0 (XXlcRS_0 (EPSILON_0 EPSILON))))))))))))))""", tree=True, options=["expansions", "quiet"])

    parser = CTFParser(grammar, top="ROOT_0", mode="lex",
                       #queueLimit=5e5,
                       verbose=["index", "level", tpar],
                       gammas=[1e-11, 1e-10, 1e-9, 1e-8],
                       deltas=[1e-5, 1e-5, 1e-5],
                       stepExpansionLimit=100)

#    sent = "The stocks fell ."
#    sent = "John Smith and Mary Roe are friends ."

    sent = "Food prices are expected to be unchanged , but energy costs jumped as much as 4 % , said Gary Ciminero , economist at Fleet\/Norstar Financial Group ."

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
