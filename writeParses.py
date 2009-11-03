from Hogwash import Session #main hogwash class
from Hogwash.Results import ResultsFile #type for file created by hw job
from Hogwash.Action import Action #supertype for runnable objects
from Hogwash.Errors import BadExitCode #error if the program crashed
from waterworks.Processes import bettersystem #run an external command

import sys
from path import path
import os
from shutil import copy
from iterextras import batch

from StringIO import StringIO #store output of process

from distributedParser import Parse
from topdownParser import Parser, Grammar, treeToStr, normalizeTree

if __name__ == "__main__":
    session = Session(sys.argv[1], read_only=True, verbose=0)

    p = Parser(Grammar({}))

    for job in session[:100]:
        if job.status != "finished":
            sent = job.args[0].sentence
            fail = p.parseFail(sent)
            print treeToStr(normalizeTree(fail.tree()))
        else:
            print job.results
