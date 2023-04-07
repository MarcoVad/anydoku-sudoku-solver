'''
Created on 4 dec. 2022

@author: marco

Console application to solve (potentially) all kinds of Sudoku puzzles. 
Run it in a terminal with ANSI color support: python3 anydoku.py <arguments> 

This file is a wrapper around the classes that do the real work:

* BoardReader: reader for anydoku JSON files. 
    You have to write a JSON file to define a puzzle you want to get solved. 
    To get started, please check the example files (notably the regular.json) 

* SudokuBoard: Base class, tool box with operations and helper functions in the scope of a single Sudoku board. 
    The data tables and operation break-down are designed to be as general and flexible as possible.
    For example, a 'field' is implemented as a group of cells that contain all numbers ('digits') once.
    This can then be handled equally for the square fields in a regular Sudoku, extra fields, diagonal fields, jigsaw fields etc.
    Calcudoku puzzles are supported by CalcudokuBoard which is a sub-class of SudokuBoard. This sub-classing is an example
    of extending the features of the base class. You can also define a sub-class to implement new features. The idea is though 
    to merge new features into the base class at some point, so that puzzles using multiple features can be solved. 
    It also supports a brute force solver for simple puzzles.

Further functions in this file:

* command line parser
    Run 'python3 anydoku.py -h' for help on the command line arguments

* merge_overlaps(): Used to merge the results of puzzles with multiple overlapping boards
    Since the SudokuBoard and sub-classes operate on single boards the merging is done here. This also means that boards of 
    different types can be successfully merged. 
    
* deduction_loop(): iterative deduction solver
    The solver loops over these operations for each board in the puzzle:
    1. get candidates:    determine which digits can be placed in each cell
    2. merge_overlaps:    does nothing unless there are overlapping boards 
    3. prune candidates:  tries to eliminate digits per cell
    4. find solutions:    detects where cells can be fixed 
    
* guessing_loop(): wraps the deduction loop and starts guessing if needed

General remarks:

* This is a pure python implementation with virtually no external dependencies.
    * only a few python modules are needed (run 'pip install -r requirements.txt') 
    * Has the benefit to be easy to understand and extend (this is work in progress, any help is welcome ;-)
    * Is cross-platform
    * Execution speed is always a concern with Python. Therefore the implementation focuses on optimized algorithms and the 
      reduction of table sizes and unnecessary loops. The larger example puzzles have been used to detect bottle necks.

* Sudoku boards are represented in a text console
    * Uses best-effort ASCII art to print the boards in progress
    * This has certainly its limitations but does the job well with the help of color mappings
    * A graphical wrapper would be a good idea though, but that's a project in itself ...  
    
--> I hope you enjoy it!

'''


import argparse
from copy import deepcopy
from Sudoku import BoardReader
try:
    from colorama import just_fix_windows_console
    just_fix_windows_console() 
except:
    print ('Some reuqired python modules are not installed\nPlease run: pip install -r requirements.txt')
    exit()

parser = argparse.ArgumentParser()
parser.add_argument('filename', help='(required) name of AnyDoku JSON file')
parser.add_argument('-v', '--verbose', default=1, type=int, help='(default 2) 0 is minimal output,  5 shows all gears in action (very noisy)')
parser.add_argument('-b', '--bruteforce', default=False, action='store_true', help='(default off) Use the brute-force method')
parser.add_argument('-m', '--maxoptions', default=1000, type=int, help='(default 300) Calcudoku optimization to postpone the evaluation of large calc fields')
conf = parser.parse_args()
verbose = conf.verbose
filename = conf.filename

try:     
    boards = BoardReader.read_from_file(filename, conf)
except BoardReader.BoardReaderError as e:
    print('ERROR reading file %s' %(filename))
    print (str(e))
    exit()

except Exception as e:
    print ("That didn't work: %s" %(e))
    #raise 
    exit()
       
        
def merge_overlaps(ibrd):
    """
    Merge the candidates of overlapping cells
    ibrd: index number of boards
    """
    updates = 0
    board = boards[ibrd]
    doku1 = board['doku']
    
    for overlap in board['overlap']:
        i, rows, rd, cols, cd = overlap 
        doku2 = boards[i]['doku']
        
        for r1 in rows:
            r2 = r1+rd
            for c1 in cols:
                c2 = c1+cd
                
                # merge candidates
                i1 = doku1.indexof(r1, c1)
                i2 = doku2.indexof(r2, c2)
                
                cand1 = doku1.cand[i1]
                cand2 = doku2.cand[i2]
                if len(cand1) == 0 or len(cand2) == 0:
                    continue
                if cand1 != cand2:
                    cand_merged = sorted(list(set(cand1).intersection(cand2)))
                    for digit in doku1.cand[i1]:
                        if digit not in cand_merged:
                            doku1.eliminate_digits(i1, [digit], doku1.cmap)
                            updates = updates+1

    return updates         

def verdict(boards):
    for board in boards:
        doku=board['doku']
        if doku.solved():
            print (doku.name + ' is solved!')
            doku.print_puzzle()
        else:
            print (doku.name + ' still has unresolved candidates')
            doku.print_candidates()
            doku.print_puzzle()
        

def deduction_loop():
    """
    Try to solve all puzzles with solver deduction, no guessing
    """    
    loop = 0
    markcolor = 4 # to mark only the latest changes
    while 1:
        loop = loop+1
        if verbose > 0 :print ('Deduction iteration', loop)
        
        upd = 0
        for i, board in enumerate(boards):
            doku=board['doku']
            
            if not doku.solved():
                
                cand = doku.get_candidates()
                if verbose > 1: doku.print_candidates(info='candidates after get_candidates()')
                
                cmap_prune = deepcopy(doku.cmap)
                merged = merge_overlaps(i)
                if verbose > 1 and merged > 0:
                    doku.print_candidates(info='candidates after merge_overlaps()')
                
                pruned = doku.prune_candidates(markcolor=markcolor, cmap=cmap_prune, verbose=verbose>1)
                if verbose > 1 and pruned > 0:
                    doku.print_candidates(cmap=cmap_prune, info='candidates after prune_candidates()')
                
                solved = doku.find_solutions(markcolor=markcolor, verbose=verbose>1)
                
                if verbose > 0: 
                    print()
                    print ("%s deduction iteration %d: candidates %s, merged %s, pruned %d, solved %d" %(doku.name, loop, cand, merged, pruned, solved))
                    print()
                    doku.print_puzzle()
                    print()
            
                doku.cmap_replace(doku.cmap, markcolor, 2)
                doku.cmap_replace(doku.cmap, 6, 0)
                upd = upd + solved
        
        if len(boards) > 1:       
            print ("overall solved", upd)
        if upd == 0:
            break
        
    psolved = 0
    for i, board in enumerate(boards):
        doku=board['doku']
        if doku.solved():
            psolved = psolved+1
    print ('solved puzzles', psolved)
    return psolved == len(boards)


def guessing_loop():
    """
    Try to solve all puzzles with solver deduction and guessing if needed
    """    
    loop = 0
    while 1:
        loop = loop+1
        
        if deduction_loop():
            print ('DONE')
            break
        
        upd = 0
        print ('Guessing iteration', loop)
        for board in boards:
            doku=board['doku']
            if not doku.solved():
                print ("deepdive into", doku.name)
                upd = upd+doku.deepdive(verbose=verbose)            
            
        if upd == 0:
            break

if conf.bruteforce:
    doku = boards[0]['doku']
    doku.bruteforce()
else:
    guessing_loop()
    verdict(boards)

