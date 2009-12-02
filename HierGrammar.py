from __future__ import division
import sys
import cPickle as pickle
from gzip import GzipFile
import shelve

from AIMA import DefaultDict
from Probably import assert_valid_prob

from topdownParser import Grammar, Rule
from DBGrammar import DBGrammar

from path import path

class HierRule(Rule):
    def __init__(self, level, string=None):
        Rule.__init__(self, string)

        self.children = []
        self.level = level

    def descendant(self, other, hierarchy):
        if hierarchy[self.level][self.lhs] != other.lhs:
            return False

        if len(self.rhs) != len(other.rhs):
            return False

        for sym,otherSym in zip(self.rhs, other.rhs):
            if hierarchy[self.level][sym] != otherSym:
                return False
        return True            

class HierGrammar(DBGrammar):
    def __init__(self, dirname, mode="r"):
        DBGrammar.__init__(self, dirname, mode)

        self.intermedRules = DefaultDict(DefaultDict([]))
        self.intermedTerminalRules = DefaultDict(DefaultDict([]))

        if mode == "w":
            self.hierarchy = DefaultDict({}) #level -> sym -> parentSym
        else:
            assert((self.dirname/"hierarchy").exists())
            self.hierarchy = pickle.load(file(self.dirname/"hierarchy", 'rb'))

    def depth(self):
        return 1 + len(self.hierarchy)

    def addAncestry(self, childLevel, parent, child):
        self.hierarchy[childLevel][child] = parent

    def makeMapping(self, topLevel):
        self.pennToLevel = DefaultDict({})
        for nt in self.hierarchy[topLevel + 1]:
            level = topLevel + 1
            ntPar = nt
            while level > 0:
                par = self.hierarchy[level][ntPar]
                self.pennToLevel[level][nt] = par

                ntPar = par
                level -= 1

    def transform(self, level, tree):
        if type(tree) is not tuple:
            return tree
        lhs = tree[0]
        if lhs not in self.pennToLevel[level]:
            par = lhs
        else:
            par = self.pennToLevel[level][lhs]
        return tuple([par,] + [self.transform(level, st) for st in tree[1:]])

    def writeback(self, target):
        if target == "hierarchy":
            hierOut = file(self.dirname/"hierarchy", 'wb')
            px = pickle.Pickler(hierOut, protocol=2)
            px.dump(self.hierarchy)

            return

        DBGrammar.writeback(self, target)

        if target == "grammar":
            self.intermedRules = DefaultDict(DefaultDict([]))

        elif target == "terminals":
            self.intermedTerminalRules = DefaultDict(DefaultDict([]))

        elif target == "epsilons":
            self.intermedRules = DefaultDict(DefaultDict([]))            

    def matchRule(self, rule, rules):
        try:
            parLHS = self.hierarchy[rule.level][rule.lhs]
        except KeyError:
            print "Error with", rule
            print "No parent of", rule.lhs, "at", rule.level
            print self.hierarchy[rule.level]
            raise
        possMatches = rules[parLHS]

        #print "Looking for ancestor of ", rule, "level", rule.level
        #print "Parent", parLHS
        #print possMatches

        for possPar in possMatches:
            if rule.descendant(possPar, self.hierarchy):
                return possPar
        return None

    def matchTermRule(self, rule, rules):
        possMatches = rules[rule.rhs[0]]

        parLHS = self.hierarchy[rule.level][rule.lhs]

        #print "Looking for ancestor of ", rule, "level", rule.level
        #print "Parent", parLHS
        #print possMatches

        for possPar in possMatches:
            if parLHS == possPar.lhs:
                return possPar
        return None

    def addRule(self, rule):
        assert(not rule.epsilon())

        if rule.level == 0:
            DBGrammar.addRule(self, rule)
        else:
            #find the parent rule and add as child
            if rule.level == 1:
                parRuleTable = self.rules
            else:
                parRuleTable = self.intermedRules[rule.level - 1]

            matching = self.matchRule(rule, parRuleTable)
            if not matching:
                print >>sys.stderr, "WARNING: Can't find matching rule for",\
                      rule
            else:
                matching.children.append(rule)

#            print "matching rule for", rule, "is", matching

            self.intermedRules[rule.level][rule.lhs].append(rule)

    def addTerminalRule(self, rule):
        assert(rule.unary())

        if rule.level == 0:
            DBGrammar.addTerminalRule(self, rule)
        else:
            #find the parent rule and add as child
            if rule.level == 1:
                parRuleTable = self.terminalRules
            else:
                parRuleTable = self.intermedTerminalRules[rule.level - 1]

            matching = self.matchTermRule(rule, parRuleTable)
            if not matching:
                print >>sys.stderr, "WARNING: Can't find matching rule for",\
                      rule
                parRule = HierRule(rule.level - 1)
                parRule.setup(rule.lhs, rule.rhs, rule.prob)
                self.addTerminalRule(parRule)
                matching = parRule

            matching.children.append(rule)

            word = rule.rhs[0]
            self.intermedTerminalRules[rule.level][word].append(rule)

    def addEpsilonRule(self, rule):
        assert(rule.epsilon())

        if rule.level == 0:
            DBGrammar.addRule(self, rule)
        else:
            if rule.level == 1:
                parLHS = self.hierarchy[rule.level][rule.lhs]
                matching = self.epsilonRules[parLHS]
                if matching:
                    assert(rule.descendant(matching, self.hierarchy))
            else:
                parRuleTable = self.intermedRules[rule.level - 1]
                matching = self.matchRule(rule, parRuleTable) 

            if not matching:
                print >>sys.stderr, "WARNING: Can't find matching rule for",\
                      rule
            else:
                matching.children.append(rule)

            self.intermedRules[rule.level][rule.lhs].append(rule)

    def addWordLookahead(self, nt, word, prob, level):
        DBGrammar.addWordLookahead(self, (level, nt), word, prob)

    def addLambdas(self, lambdas, level):
        for k,v in lambdas.items():
            self.lambdas[(level, k)] = v

    def addNTToPos(self, ntToPos, level):
        for k,v in ntToPos.items():
            self.ntToPos[(level, k)] = v

    def lookaheadProbFull(self, nt, word, level):
        presplit = nt.split("_")[0]
        try:
            lamb = self.lambdas[presplit]
        except KeyError:
            lamb = 0.5
        return Grammar.lookaheadProbFull(self, (level, nt), word, lamb=lamb)

    def lookaheadProb(self, nt, word, level=0):
        try:
            return self.lookaheadCache[(level, nt)][word]
        except KeyError:
            #note: caused because nt is a POS tag, and we didn't
            #load any rules which use it, because it can't
            #produce any word in this sentence
            #therefore, parses containing it automatically suck
            return 0

    def preload(self, sent):
        self.terminalRules = DefaultDict({})
        for word in sent:
            wordRules = self.terminalDB[word]

            for rule in wordRules:
                self.terminalRules[rule.lhs][word] = rule

        self.ntToWord = DefaultDict({})
        for word in sent:
            try:
                wordLook = self.ntToWordDB[word]

                for nt,prob in wordLook.items():
                    self.ntToWord[nt][word] = prob
            except KeyError:
                print >>sys.stderr, "WARNING: no word lookaheads for", word

        self.posToWord = DefaultDict({})
        for word in sent:
            try:
                posLook = self.posToWordDB[word]

                for pos,prob in posLook.items():
                    self.posToWord[pos][word] = prob
            except KeyError:
                print >>sys.stderr, "WARNING: no pos lookaheads for", word

                #derive from the grammar; maybe this is always a better idea?
                wordRules = self.terminalDB[word]

                for rule in wordRules:
                    pos = rule.lhs.split("_")[0]
                    if word not in self.posToWord[pos]:
                        self.posToWord[pos][word] = 0
                    self.posToWord[pos][word] += rule.prob

#         print >>sys.stderr, self.epsilonRules

        self.lookaheadCache = DefaultDict({})
        #add None to load probs for epsilon productions
        for word in sent + [None,]:
            level = 0
            for nt in self.rules.keys() + self.epsilonRules.keys():
                lap = self.lookaheadProbFull(nt, word, level)
                #print >>sys.stderr, "at level", level,\
                #      nt, "->", word, "=", lap
                self.lookaheadCache[(level, nt)][word] = lap

            for level in self.hierarchy:
#                print >>sys.stderr, "computing lookaheads for", level
                for nt in self.hierarchy[level]:
                    lap = self.lookaheadProbFull(nt, word, level)
#                     print >>sys.stderr, "at level", level,\
#                           nt, "->", word, "=", lap
                    self.lookaheadCache[(level, nt)][word] = lap

    def preloadPOSOnly(self, sent):
        self.terminalRules = DefaultDict({})
        self.ntToWord = DefaultDict({})
        self.posToWord = DefaultDict({})

        self.lookaheadCache = DefaultDict({})
        #add None to load probs for epsilon productions
        for pos in sent + [None,]:
            level = 0
            for nt in self.rules.keys() + self.epsilonRules.keys():
                lap = self.lookaheadProbFullPOS(nt, pos, level)
#                 print >>sys.stderr, "at level", level,\
#                       nt, "->", pos, "=", lap
                self.lookaheadCache[(level, nt)][pos] = lap

            for level in self.hierarchy:
#                print >>sys.stderr, "computing lookaheads for", level
                for nt in self.hierarchy[level]:
                    lap = self.lookaheadProbFullPOS(nt, pos, level)
#                     print >>sys.stderr, "at level", level,\
#                           nt, "->", word, "=", lap
                    self.lookaheadCache[(level, nt)][pos] = lap

    def lookaheadProbFullPOS(self, nt, pos, level):
        nt = (level, nt)
        #eqn 3.30 from Roark
        if pos is None:
            #XXX hardcoded name of epsilon nonterm
            try:
                res = self.ntToPos[nt]["EPSILON"]
                #print >>sys.stderr, nt, "to epsilon", res
                return res
            except KeyError:
                return 0

        try:
            term = self.ntToPos[nt][pos]
        except KeyError:
            term = 0

        assert_valid_prob(term)
        return term
