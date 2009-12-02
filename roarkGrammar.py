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

from treeUtils import markovBinarizeTree, treeToTuple, treeToStr, zeroSplit
from ctfScheme import leftCorner, GrammarStats, ValidationEvents

if __name__ == "__main__":
    (out, trees, validation) = sys.argv[1:]

    print "Output:", out, "Training:", trees, "Validation:", validation

    grammar = HierGrammar(out, mode='w')
    binarizeTo = 0

    gstats = GrammarStats()
    vstats = ValidationEvents()

    for ct,line in enumerate(file(trees)):
        if ct % 100 == 0:
            print "read trees", ct
        tree = markovBinarizeTree(treeToTuple(line.strip()), to=0)

#        print treeToStr(tree)
        gstats.record(tree)

    for ct,line in enumerate(file(validation)):
        if ct % 100 == 0:
            print "read validation trees", ct
        tree = markovBinarizeTree(treeToTuple(line.strip()), to=0)
        vstats.record(tree)

    gstats.normalize()
    gstats.learnLambdas(vstats)
    gstats.addToGrammar(grammar, 0)

    grammar.writeback("hierarchy")
    grammar.writeback("grammar")
    grammar.writeback("terminals")
    grammar.writeback("epsilons")
    grammar.writeback("lookahead")
    grammar.writeback("ntToWord")
    grammar.writeback("posToWord")
    
