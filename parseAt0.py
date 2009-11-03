from __future__ import division
import sys
import cPickle as pickle
from gzip import GzipFile

from AIMA import DefaultDict

from topdownParser import Grammar, Rule, Parser, normalizeTree, treeToStr
from DBGrammar import DBGrammar
from HierGrammar import HierGrammar

if __name__ == "__main__":
    inf = sys.argv[1]

    print >>sys.stderr, "loading grammar", inf

    grammar = HierGrammar(inf)

    print >>sys.stderr, "done"

    debug = ["index", "pop", "push", "threshold"]
    parser = Parser(grammar, top="ROOT_0", mode="lex",
                    queueLimit=5e5,
                    verbose=["index", "pop", "push", "lookahead"])

#    sent = "The stocks fell ."
    sent = "The government 's plan is stupid ."
#    sent = "John Smith and Mary Roe are friends ."

    final = parser.parse(sent.split())
    print final
    print list(final.derivation())
    print treeToStr(final.tree())
    print treeToStr(normalizeTree(final.tree()))
    print treeToStr(final.tree(True))
