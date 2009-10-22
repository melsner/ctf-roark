from __future__ import division
import sys
import cPickle as pickle
from gzip import GzipFile

from AIMA import DefaultDict

from topdownParser import Grammar, Rule, Parser, normalizeTree, treeToStr
from DBGrammar import DBGrammar

if __name__ == "__main__":
    inf = sys.argv[1]

    print >>sys.stderr, "loading grammar", inf

    grammar = DBGrammar(inf)

    print >>sys.stderr, "done"

    debug = ["index", "pop", "push", "threshold"]
    parser = Parser(grammar, top="ROOT_0", mode="lex",
                    queueLimit=5e5,
                    verbose=["index"])

    sent = "The stocks fell ."
#    sent = "Members of the House Ways and Means Committee introduced legislation that would restrict how the new savings-and-loan bailout agency can raise capital , creating another potential obstacle to the government 's sale of sick thrifts ."
#    sent = "The government 's plan"
#    sent = "John Smith and Mary Roe are friends ."

    #import cProfile
    #final = cProfile.run('parser.parse(sent.split())', 'profile-out4')

    final = parser.parse(sent.split())
    print final
    print list(final.derivation())
    print treeToStr(final.tree())
    print treeToStr(normalizeTree(final.tree()))
    print treeToStr(final.tree(True))
