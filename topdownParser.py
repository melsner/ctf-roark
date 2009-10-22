from __future__ import division
import heapq
from AIMA import DefaultDict
import sys
from copy import deepcopy, copy
from math import log, exp

from Probably import assert_valid_prob

if True: #use psyco
    try:
        import warnings
        warnings.simplefilter("ignore", RuntimeWarning)
        from psyco.classes import psyobj
        warnings.simplefilter("default", RuntimeWarning)
    except ImportError:
        print >>sys.stderr, "WARNING: can't load psyco!"
        class psyobj(object):
            pass
else:
    class psyobj(object):
        pass

from debugging import reportMatchingParses
from rule import Rule

class ParseError(Exception):
    def __init__(self, msg):
        Exception.__init__(self, msg)

class Grammar(psyobj):
    def __init__(self, rules):
        self.lambdas = None
        self.ntToPos = None
        self.ntToWord = None
        self.posToWord = None
        
        self.terminalRules = DefaultDict({})
        self.rules = DefaultDict([])

        for lhs,ruleList in rules.items():
            for rule in ruleList:
                #this is a poor way to figure out terminal rules!
                #kept only because it won't ever get called
                #except in toy code
                if rule.unary() and rule.rhs[0].islower():
                    self.terminalRules[rule.lhs][rule.rhs[0]] = rule
                else:
                    #epsilon must go in this category, since
                    #deriving should always return it
                    self.rules[rule.lhs].append(rule)

    def depth(self):
        return 1

    def preload(self, sent):
        self.lookaheadCache = DefaultDict({})
        for word in sent:
            for nt in (self.rules.keys() + self.terminalRules.keys()):
                #print nt, word
                lap = self.lookaheadProbFull(nt, word)
                #print lap
                self.lookaheadCache[nt][word] = lap

    def deriving(self, sym, word):
        #perhaps this will run faster if it doesn't use coroutines?
        res = []
        for rule in self.rules[sym]:
            rule.terminal = False
            res.append(rule)
        wordRule = self.terminalRules[sym].get(word)
        if wordRule:
            wordRule.terminal = True
            res.append(wordRule)
        return res        

#     def deriving(self, sym, word):
#         for rule in self.rules[sym]:
#             rule.terminal = False
#             yield rule
#         wordRule = self.terminalRules[sym].get(word)
#         if wordRule:
#             wordRule.terminal = True
#             yield wordRule

    def setLookahead(self, lambdas, ntToPos, ntToWord, posToWord):
        self.lambdas = lambdas
        self.ntToPos = ntToPos
        self.ntToWord = ntToWord
        self.posToWord = posToWord

    def lookaheadProb(self, nt, word, level):
        try:
            return self.lookaheadCache[nt][word]
        except KeyError:
            #note: caused because nt is a POS tag, and we didn't
            #load any rules which use it, because it can't
            #produce any word in this sentence
            #therefore, parses containing it automatically suck
            return 0

    def lookaheadProbFull(self, nt, word, lamb=None):
        #eqn 3.30 from Roark
        if lamb == None and not self.lambdas:
            return 1.0

        if lamb == None:
            lamb = self.lambdas[nt]

        try:
            pGivenWord = self.ntToWord[nt][word]
        except KeyError:
            pGivenWord = 0

        pGivenPos = 0
        for pos in self.posToWord:
            try:
                term = self.ntToPos[nt][pos] * self.posToWord[pos][word]
            except KeyError:
                term = 0
            pGivenPos += term

        assert_valid_prob(pGivenWord)
        assert_valid_prob(pGivenPos)

        res = lamb * pGivenWord + (1 - lamb) * pGivenPos

        assert_valid_prob(res)

        return res

    def __repr__(self):
        return repr(self.rules)

class Analysis(psyobj):
    def __init__(self, top="ROOT", initial=False):
        self.deriv = None
        self.parent = None
        self.localStack = []
        if initial:
            self.localStack.append(top)
        #note: probs are negative because python provides a minheap
        #so smaller numbers have to be better
        self.prob = -1.0
        self.fom = -1.0
        self.lap = 1.0
        self.word = 0

    def level(self):
        return 0

    def derivation(self):
        if self.parent:
            for dd in self.parent.derivation():
                yield dd
        if self.deriv:
            yield self.deriv

    def stackTop(self, ind=0):
        if len(self.localStack) > ind:
            return self.localStack[ind]
        elif self.parent:
            return self.parent.stackTop(ind + 1 - len(self.localStack))
        else:
            return None

    def stack(self):
        for ss in self.localStack:
            yield ss
        if self.parent:
            first = True
            for ss in self.parent.stack():
                if first:
                    first = False
                else:
                    yield ss

    def __repr__(self):
        return "%s, %.3g %.3g" % (" ".join(self.stack()),
                                  -self.prob, -self.fom)

    def __cmp__(self, other):
        if self is other:
            return 0
        res = cmp(self.fom, other.fom)
        if res == 0:
            return cmp(id(self), id(other))
        return res

    def __hash__(self):
        return hash(id(self))

    def clone(self):
        ana = Analysis()
        ana.parent = self

        ana.prob = self.prob
        ana.word = self.word
        return ana

    def extend(self, rule, word, nextWord, parser, doFOM=True):
        rhs = rule.rhs
        ruleProb = rule.prob

        newAnalysis = self.clone()
        newAnalysis.prob *= ruleProb
        newAnalysis.deriv = rule

        if rhs == [word,]:
            newAnalysis.word += 1
            lookWord = nextWord
        else:
            lookWord = word
            newAnalysis.localStack = rhs

        if doFOM:
            newAnalysis.lap = parser.lookahead(newAnalysis, lookWord)
            newAnalysis.fom = (newAnalysis.prob * newAnalysis.lap)

        assert(-1 <= newAnalysis.prob <= 0)
        assert(-1 <= newAnalysis.fom <= 0)

        return newAnalysis

    def tree(self, annotateProbs=False, allowPartial=False):
        return self.treeHelper(list(self.derivation()), annotateProbs,
                               allowPartial)

    def treeHelper(self, deriv, annotateProbs, allowPartial):
        try:
            rule = deriv.pop(0)
        except IndexError:
            if allowPartial:
                if annotateProbs:
                    return ("...", 0.0)
                else:
                    return ("...",)
            else:
                raise

        if annotateProbs:
            p = log(rule.prob)

            if rule.epsilon():
                return (rule.lhs, p, None)
            elif rule.terminal:
                return (rule.lhs, p, rule.rhs[0])
            elif rule.unary():
                st = self.treeHelper(deriv, annotateProbs, allowPartial)
                return (rule.lhs, st[1] + p, st)
            else:
                st1 = self.treeHelper(deriv, annotateProbs, allowPartial)
                st2 = self.treeHelper(deriv, annotateProbs, allowPartial)
                p += st1[1] + st2[1]
                return (rule.lhs, p, st1, st2)

        if rule.epsilon():
            return (rule.lhs, None)
        elif rule.terminal:
            return (rule.lhs, rule.rhs[0])
        elif rule.unary():
            return (rule.lhs, self.treeHelper(deriv, annotateProbs,
                                              allowPartial))
        else:
            return (rule.lhs,
                    self.treeHelper(deriv, annotateProbs, allowPartial),
                    self.treeHelper(deriv, annotateProbs, allowPartial))

def treeToStr(tree):
    if type(tree) != tuple:
        return str(tree)
    return "(%s %s)" % (tree[0], " ".join([treeToStr(x) for x in tree[1:]]))

def normalizeTree(tree, stripSub=True):
    return normalizeTreeHelper(tree, stripSub)[0]

def normalizeTreeHelper(tree, stripSub):
    if type(tree) != tuple:
        return [tree,]
    if tree[1] is None:
        return []

    label = tree[0]
    if stripSub:
        label = label.split("_")[0]
    if label.startswith("@"):
        res = []
        for sub in tree[1:]:
            ntree = normalizeTreeHelper(sub, stripSub)
            for constit in ntree:
                res.append(constit)
    else:
        res = [label,]
        for sub in tree[1:]:
            ntree = normalizeTreeHelper(sub, stripSub)
            for constit in ntree:
                res.append(constit)
        res = [tuple(res)]

    return res

def identityBeamF(gamma, nOptions):
    return gamma * nOptions
def cubicBeamF(gamma, nOptions):
    return gamma * nOptions**3

def empty(it):
    for x in it:
        return False
    return True

class Parser(psyobj):
    def __init__(self, grammar, top="ROOT", queueLimit=10000,
                 beamF=identityBeamF, gamma=1e-4, mode=None, verbose=[],
                 makeAnalysis=Analysis):
        self.grammar = grammar
        self.top = top

        if mode == None:
            self.gamma = gamma
            self.beamF = beamF
        elif mode == "unlex":
            self.gamma = 1e-4
            self.beamF = identityBeamF
        elif mode == "lex":
            self.gamma = 1e-11
            self.beamF = cubicBeamF
        else:
            raise ValueError("Bad parser mode: %s" % mode)

        self.queueLimit = queueLimit

        self.makeAnalysis = makeAnalysis

        self.pushes = 0
        self.pops = 0

        self.verbose = verbose

    def parse(self, sentence):
        self.grammar.preload(sentence)

        n = len(sentence)
        
        hyps = [[] for i in range(n + 3)]
        baseAnalysis = self.makeAnalysis(top=self.top,
                                         initial=self.grammar.depth())
        hyps[0].append(baseAnalysis)

        for i in range(0, n):

            if "index" in self.verbose:
                print >>sys.stderr, "************* WORD", i, sentence[i]
            
            while self.aboveThreshold(hyps, i):
                self.generateHypotheses(hyps, i, sentence)

            if self.verbose:
                reportMatchingParses(self.verbose, hyps[i+1], 0)

            self.afterGenerating(hyps, i, sentence)
            hyps[i] = [] #try to allow gc for bad hypotheses

        if "index" in self.verbose:
            print >>sys.stderr, "************* EMPTYING STACKS"

        while self.aboveThreshold(hyps, n):
            self.generateFinalHypotheses(hyps, n)
        self.afterGenerating(hyps, n, sentence)

        if "index" in self.verbose:
            print >>sys.stderr, "************* COMPLETE"
        
        if hyps[n + 1]:
            return hyps[n + 1][0]

        raise ParseError("Can't parse: %s" % sentence)

    def afterGenerating(self, hyps, i, sentence):
        #useful in derived class
        pass

    def aboveThreshold(self, hyps, i):
        if not hyps[i]:

            if "threshold" in self.verbose:
                print >>sys.stderr, "--no more hypotheses"
            
            return False

        if len(hyps[i]) > self.queueLimit:
            if "threshold" in self.verbose:
                print >>sys.stderr, "--cannot accept any more hypotheses"
            
            return False

        expandNext = hyps[i][0]

        if not hyps[i + 1]:

            if "threshold" in self.verbose:
                print >>sys.stderr, "--accept (no comparison)"

            return True

        bestOption = hyps[i + 1][0].fom
        nOptions = len(hyps[i + 1])

        beam = bestOption * self.beamF(self.gamma, nOptions)

        if "threshold" in self.verbose:
            print >>sys.stderr, \
                  "--merit %g, beam >= %g, curr %d, next %d" % (
                bestOption, beam, len(hyps[i]), nOptions)

        #- sign because minheap so everything is negative
        return expandNext.fom <= beam

    def generateHypotheses(self, hyps, i, sentence):
        expandNext = heapq.heappop(hyps[i])
        currentWord = sentence[expandNext.word]
        try:
            nextWord = sentence[expandNext.word + 1]
        except IndexError:
            nextWord = None

        if "pop" in self.verbose:
            print >>sys.stderr, "popped", expandNext

        if expandNext.stackTop() == None:
            #grammar expected end of sentence at previous word
            return

        expandSym = expandNext.stackTop()

        for rule in self.grammar.deriving(expandSym, currentWord):
            if rule.terminal and not rule.unaryMatch(currentWord):
                assert(False), "Can't happen!"
                continue
            
            if "push" in self.verbose:
                print >>sys.stderr, "rule", rule

            newAnalysis = expandNext.extend(rule, currentWord,
                                            nextWord, self)

            if "push" in self.verbose:
                print >>sys.stderr, "pushed", newAnalysis, \
                      "onto", newAnalysis.word
            
            heapq.heappush(hyps[newAnalysis.word], newAnalysis)
            self.pushes += 1

    def generateFinalHypotheses(self, hyps, i):
        expandNext = heapq.heappop(hyps[i])
        self.pops += 1

        if "pop" in self.verbose:
            print >>sys.stderr, "popped", expandNext

        if expandNext.stackTop() == None:
            if "push" in self.verbose:
                print >>sys.stderr, "parsed", expandNext
            
            heapq.heappush(hyps[i + 1], expandNext)
            self.pushes += 1
        else:
            expandSym = expandNext.stackTop()

            for rule in self.grammar.deriving(expandSym, None):
                if "push" in self.verbose:
                    print >>sys.stderr, "rule", rule

                newAnalysis = expandNext.extend(rule, None, None, self)

                if "push" in self.verbose:
                    print >>sys.stderr, "pushed", newAnalysis
                
                heapq.heappush(hyps[newAnalysis.word], newAnalysis)
                self.pushes += 1

    def lookahead(self, analysis, nextWord):
        #3.29 from Roark
        #currently doesn't believe in epsilon
        if analysis.stackTop() == None:
            if nextWord is None:
                return 1.0
            else:
                return 0.0
        stackTop = analysis.stackTop()

        if stackTop == nextWord:
            return 1.0

        #if we can do it in one step, just do it!
        wordRule = self.grammar.terminalRules[stackTop].get(nextWord)
        if wordRule:
            return wordRule.prob

        res = self.grammar.lookaheadProb(stackTop, nextWord,
                                         analysis.level())

        if "lookahead" in self.verbose:
            print >>sys.stderr, "Lookahead: ", stackTop, nextWord,\
                  analysis.level(), "=", res

        return res

    def parseFail(self, sentence):
        top = self.top
        topBar = "@%s" % top
        lhs = top
        ana = self.makeAnalysis(top=top, initial=self.grammar.depth())

        for word in sentence:
            posInsRule = Rule()
            posInsRule.setup(lhs, ["FW", topBar], 1.0)
            lhs = topBar
            posInsRule.terminal = False
            ana = ana.extend(posInsRule, None, None, self, doFOM=False)
            wordInsRule = Rule()
            wordInsRule.setup("FW", [word,], 1.0)
            wordInsRule.terminal = True
            ana = ana.extend(wordInsRule, None, None, self, doFOM=False)

        endRule = Rule()
        endRule.setup(topBar, [], 1.0)
        endRule.terminal = True
        ana = ana.extend(endRule, None, None, self, doFOM=False)

        return ana

def processGrammar(grammar):
    rules = DefaultDict([])
    for line in grammar.split("\n"):
        if line.strip():
            rule = Rule(line)
            rules[rule.lhs].append(rule)

    #renormalize the rules to make a pcfg
    for cat,rlist in rules.items():
        tot = sum(x.prob for x in rlist)
        for rule in rlist:
            rule.prob /= tot

    return rules

if __name__ == "__main__":
    grammar = """
    1.0 S -> NP VP
    1.0 NP -> DT NN
    1.0 VP -> V NP
    1.0 DT -> the
    1.0 NN -> moon
    1.0 NN -> sun
    1.0 V -> is
    """

    debug = ["index", "pop", "push", "threshold"]

    if 0:
        rules = Grammar(processGrammar(grammar))

        print rules

        parser = Parser(rules, top="S", verbose=debug)
        final = parser.parse("the moon is the sun".split())
        print final
        print list(final.derivation())
        print treeToStr(final.tree())
        print treeToStr(normalizeTree(final.tree()))

    if 0:
        grammar = """
        1.0 S -> NP VP
        1.0 NP -> DT NPSUB
        1.0 NPSUB -> NN NPEND
        1.0 NPEND ->
        1.0 VP -> V NP
        1.0 DT -> the
        1.0 NN -> moon
        1.0 NN -> sun
        1.0 V -> is
        """

    if 1:
        grammar2 = grammar + """
        1.0 NP -> NP PP    
        1.0 PP -> IN NP
        1.0 IN -> of
        1.0 NN -> night
        1.0 ROOT -> S
        """

        rules2 = Grammar(processGrammar(grammar2))
        print processGrammar(grammar2)

        print rules2

        parser = Parser(rules2, top="ROOT", verbose=["index", "pop", "threshold"])
        sent = "the moon of the moon is the moon of the moon of the moon"
        final = parser.parse(sent.split())
        print final
        print list(final.derivation())
        print treeToStr(final.tree())
        print treeToStr(normalizeTree(final.tree()))

    if 0:
        parser = Parser(rules2, top="ROOT", verbose=["index"])
        print "Fail case:"
        fail = parser.parseFail(sent.split())
        print fail
        print list(fail.derivation())
        print treeToStr(fail.tree())
        print fail.tree()
        print treeToStr(normalizeTree(fail.tree()))
