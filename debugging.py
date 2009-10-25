from __future__ import division
import sys

from StringIO import StringIO
from itertools import izip

from rule import Rule

def treeToDeriv(tree):
    if type(tree[1]) is not tuple:
        r = Rule()
        r.setup(tree[0], [tree[1],], 1.0)
        return [r,]
    else:
        r = Rule()
        rhs = [x[0] for x in tree[1:]]
        assert(len(rhs) <= 2), "Non-binary rule: %s" % str(rhs)
        r.setup(tree[0], rhs, 1.0)
        res = [r,]
        for subt in tree[1:]:
            res += treeToDeriv(subt)
        return res

def treeToTuple(tree):
    assert(tree[0] == "(")
    return treeToTupleHelper(tree, 1)[0]

def treeToTupleHelper(tbuf, ind):
    label = ""
    word = ""
    inLabel = True
    subs = []

    while ind < len(tbuf):
        char = tbuf[ind]
        #print char
        ind += 1

        if char == "(":
            #print "push", ind
            (sub, newInd) = treeToTupleHelper(tbuf, ind)
            subs.append(sub)
            #print "pop", newInd, subs
            ind = newInd
        elif char == ")":
            if word:
                return ((label, word), ind)
            else:
                assert(subs)
                return (tuple([label,]+subs), ind)
        elif char == " ":
            inLabel = False
        else:
            if inLabel:
                label += char
            else:
                word += char
    assert(False), "Malformed tree, read %s" % char

class TargetParse:
    def __init__(self, tderiv, tree=False, level=0, options=[]):
        self.level = level
        self.options = options

        if tree:
            self.derivation = treeToDeriv(treeToTuple(tderiv))
        else:
            self.derivation = []

            tderiv = tderiv.lstrip("[").rstrip("]")
            rules = tderiv.split(",")
            for ruleStr in rules:
                rule = Rule(ruleStr)
                self.derivation.append(rule)

    def matches(self, ana):
        if ana.level() != self.level:
            return False

        for myRule,theirRule in izip(self.derivation, ana.derivation()):
            #print "check", myRule, theirRule, myRule == theirRule
            if myRule != theirRule:
                return False
        return True

class DebugAnalysis:
    def __init__(self, ana, debugTarget):
        if hasattr(ana, "debugged"):
            return

        self.ana = ana
        self.debugTarget = debugTarget

        if "expansions" in debugTarget.options:
            self.extend = self.ana.extend
            self.ana.extend = self.extendHook
        if "specifications" in debugTarget.options:
            self.nextStepToSpecify = self.ana.nextStepToSpecify
            self.ana.nextStepToSpecify = self.specifyHook
        self.ana.debugged = True

    def specifyHook(self, foremost):
        print >>sys.stderr, "specifying", self.ana
        print >>sys.stderr, self.ana.expansionProfile(self.ana)
        res = self.nextStepToSpecify(foremost)
        (step, fom) = res
        print >>sys.stderr, "result:", list(step.derivation()), fom
        return res

    def extendHook(self, rule, sentence, word, nextWord, doFOM=True):
        print >>sys.stderr, "extending", self.ana, "by", rule
        res = self.extend(rule, sentence, word, nextWord, doFOM=doFOM)

        if self.debugTarget.matches(res):
            dbgChild = DebugAnalysis(res, self.debugTarget)

        print >>sys.stderr, "result was", res
        return res

def findFilters(lst):
    filterList = []

    for tt in lst:
        if hasattr(tt, "matches"):
            filterList.append(tt)

    return filterList

def reportMatchingParses(verboseList, hyps, level):
    filters = findFilters(verboseList)
    if not filters:
        return

    for i,hyp in enumerate(hyps):
        for tt in filters:
            if hyp.level() == level and tt.matches(hyp):
                print >>sys.stderr, hyp, "on level %d beam at %d" % (level, i)

#                 dlist = list(hyp.derivation())
#                 print >>sys.stderr, "!!!!", dlist
#                 prod = 1
#                 for dd in dlist:
#                     prod *= dd.prob
#                 print >>sys.stderr, "!!", prod

#                 if hyp.subLevelHeap:
#                     for subd in hyp.subLevelHeap:
#                         dlist = list(subd.derivation())
#                         print >>sys.stderr, "####", dlist
#                         prod = 1
#                         for dd in dlist:
#                             prod *= dd.prob
#                         print >>sys.stderr, "##", prod

                if ("expansions" in tt.options or
                    "specifications" in tt.options):
                    dbg = DebugAnalysis(hyp, tt)
                if "profile" in tt.options:
                    print >>sys.stderr, hyp.expansionProfile(hyp)
        if hasattr(hyp, "subLevelHeap"):
            reportMatchingParses(verboseList, hyp.subLevelHeap, level)
