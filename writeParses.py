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
    session = Session(sys.argv[1], read_only=True)

    for job in session:
        if job.status != "finished":
            break
        print job.results
