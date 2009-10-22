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

if __name__ == "__main__":
    (sessionName, fileToParse, grammar) = sys.argv[1:]

    print "making", sessionName, \
          "to parse", fileToParse, "with grammar", grammar

    parseOpts = {
        "top":"ROOT_0",
        "mode":"lex",
        "queueLimit":5e5,
        "verbose":["index",]
        }

    args = []

    for line in file(fileToParse):
        line = line.strip()
        par = Parse(grammar, parseOpts, line)
        args.append(par)

    session = Session("Hogwash.Action", "action_runner", args, name=sessionName)
