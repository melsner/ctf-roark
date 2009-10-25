from Hogwash.Results import ResultsFile #type for file created by hw job
from Hogwash.Action import Action #supertype for runnable objects
from Hogwash.Errors import BadExitCode #error if the program crashed
#get a job-specific name
from Hogwash.Helpers import make_job_output_filename, get_cpu_bitness
from waterworks.Processes import bettersystem #run an external command

from topdownParser import Grammar, Rule, Parser, ParseError, \
     normalizeTree, treeToStr
from DBGrammar import DBGrammar
from HierGrammar import HierGrammar
from ctfParser import CTFParser

from path import path
import sys

#class representing an experiment to run
class Parse(Action):
    def __init__(self, grammar, parseOpts, sentence, parser="standard"):
        self.grammar = path(grammar).abspath()
        self.parseOpts = parseOpts
        self.sentence = sentence.split()
        self.parserType = parser

    def run(self, hogwash_job):
        print >>sys.stderr, "Loading grammar", self.grammar

        grammar = HierGrammar(self.grammar)

        print >>sys.stderr, "Done"

        print >>sys.stderr, "Parse options:"
        print >>sys.stderr, self.parseOpts

        self.parseOpts["grammar"] = grammar

        if self.parserType == "standard":
            parser = Parser(**self.parseOpts)
        elif self.parserType == "ctf":
            parser = CTFParser(**self.parseOpts)
        else:
            raise TypeError("Don't know parser type %s" % self.parserType)

        print >>sys.stderr, "Parsing:", self.sentence

        try:
            final = parser.parse(self.sentence)
            res = treeToStr(normalizeTree(final.tree()))
        except (ParseError, TypeError):
            #if psyco is active, throwing a parse error will fail
            #because psyco doesn't realize that exceptions can be
            #newstyle classes, because it's *old*
            #so we get a type error
            final = parser.parseFail(self.sentence)
            res = treeToStr(normalizeTree(final.tree()))
        print res

        return res
