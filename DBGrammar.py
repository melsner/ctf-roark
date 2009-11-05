from __future__ import division
import sys
import cPickle as pickle
from gzip import GzipFile
import shelve

from AIMA import DefaultDict

from topdownParser import Grammar, Rule

from path import path

class DBGrammar(Grammar):
    def __init__(self, dirname, mode="r"):
        self.dirname = path(dirname)

        assert(mode in "rw")

        if mode == "r":
            assert((self.dirname/"grammar").exists())
            gfile = file(self.dirname/"grammar", 'rb')
            self.rules = pickle.load(gfile)

            g2file = path(self.dirname/"epsilons")
            if g2file.exists():
                g2fh = file(g2file, 'rb')
                self.epsilonRules = pickle.load(g2fh)
            else:
                print >>sys.stderr, "WARNING: grammar has no epsilon rules"
                self.epsilonRules = {}

            assert((self.dirname/"lookahead").exists())
            lookFile = file(self.dirname/"lookahead", 'rb')
            self.lambdas = pickle.load(lookFile)
            self.ntToPos = pickle.load(lookFile)            

            #these asserts seem to assume something about the
            #filenaming conventions of the underlying db
            assert((self.dirname/"terminals").exists())
            self.terminalDB = shelve.open(self.dirname/"terminals",
                                          flag='r')

            assert((self.dirname/"ntToWord").exists())
            self.ntToWordDB = shelve.open(self.dirname/"ntToWord",
                                          flag='r')

            assert((self.dirname/"posToWord").exists())
            self.posToWordDB = shelve.open(self.dirname/"posToWord",
                                           flag='r')
        else:
            if not self.dirname.exists():
                self.dirname.mkdir()
            
            self.rules = DefaultDict([])
            self.epsilonRules = {}
            self.lambdas = {}
            self.ntToPos = DefaultDict({})

            self.terminalDB = shelve.open(self.dirname/"terminals",\
                                          flag='c', protocol=2)
            self.ntToWordDB = shelve.open(self.dirname/"ntToWord",\
                                          flag='c', protocol=2)
            self.posToWordDB = shelve.open(self.dirname/"posToWord",\
                                         flag='c', protocol=2)

            self.terminalRules = DefaultDict([])
            self.ntToWord = DefaultDict({})
            self.posToWord = DefaultDict({})

    def __del__(self):
        self.terminalDB.close()
        self.ntToWordDB.close()
        self.posToWordDB.close()

    def writeDB(self, table, db):
        for ct,(k,v) in enumerate(table.items()):
            db[k] = v

            if ct % 1000 == 0:
                print >>sys.stderr, "wrote", ct
        db.close()

    def writeback(self, target):
        if target == "grammar":
            ruleOut = file(self.dirname/"grammar", 'wb')
            px = pickle.Pickler(ruleOut, protocol=2)
            px.dump(self.rules)
            self.rules = None

        elif target == "epsilons":
            epsilonsOut = file(self.dirname/"epsilons", 'wb')
            px = pickle.Pickler(epsilonsOut, protocol=2)
            px.dump(self.epsilonRules)
            self.epsilonRules = None

        elif target == "lookahead":
            lookOut = file(self.dirname/"lookahead", 'wb')
            px = pickle.Pickler(lookOut, protocol=2)
            px.dump(self.lambdas)
            px.dump(self.ntToPos)

            self.lambdas = None
            self.ntToPos = None

        elif target == "terminals":
            self.writeDB(self.terminalRules, self.terminalDB)
            self.terminalRules = None
            
        elif target == "ntToWord":
            self.writeDB(self.ntToWord, self.ntToWordDB)
            self.ntToWord = None

        elif target == "posToWord":
            self.writeDB(self.posToWord, self.posToWordDB)
            self.posToWord = None

        else:
            assert(0), "Bad write mode!"

    def addRule(self, rule):
        if rule.epsilon():
            assert(rule.lhs not in self.epsilonRules)
            self.epsilonRules[rule.lhs] = rule
        else:
            self.rules[rule.lhs].append(rule)

    def addTerminalRule(self, rule):
        assert(rule.unary())
        word = rule.rhs[0]

        self.terminalRules[word].append(rule)

    def addWordLookahead(self, nt, word, prob):
        self.ntToWord[word][nt] = prob

    def addPosToWord(self, pos, word, prob):
        self.posToWord[word][pos] = prob

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
            posLook = self.posToWordDB[word]

            for pos,prob in posLook.items():
                self.posToWord[pos][word] = prob

        Grammar.preload(self, sent)

    def lookaheadProbFull(self, nt, word):
        presplit = nt.split("_")[0]
        try:
            lamb = self.lambdas[presplit]
        except KeyError:
            lamb = 0.5
        return Grammar.lookaheadProbFull(self, nt, word, lamb=lamb)
