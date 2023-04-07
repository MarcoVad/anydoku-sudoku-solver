'''
Created on 4 dec. 2022

@author: marco
'''
from copy import deepcopy
import time
import re
from math import sqrt
from Sudoku.colors import *

# color map for cells:
# 0 : empty cell
# 1 : given digit
# 2 : found digit
# 3 : unstable
# 4 : changed cell
# 5 : trying a digit
# 6 : pruned candidates 
color = ['', bg_yellow+bright, fg_cyan+bright, fg_red, bg_green, blink, bg_magenta]

efieldcolors = ["\033[48;5;243m", "\033[48;5;240m"] 
oddevencolors = {
    '.': '',
    'O': "\033[48;5;17m",
    'E': "\033[48;5;52m"}

#oddevencolors = {
#    '.': '',
#    'O': "\033[48;5;60m",
#    'E': "\033[48;5;94m"}

VERBOSE = 0
DEBUG = False
t = time.time()


class SudokuBoard(object):

    def __init__(self, board, conf):
        """
        Base class constructor for SudokuBoard
        board: dictionary containing the board details 
        """
        self.conf = conf
        self.name = board['name']
        self.puz = []
        for item in board['puzzle']:
            if type(item) == list: 
                self.puz.extend(item)
            else:
                self.puz.append(item)

        global RS, CS 
        RS = board['rowsize']
        CS = board['colsize']
        self.size = RS*CS
        self.digits = board.get('digits', self.guess_digits(self.puz))
        
        self.rowsize = RS
        self.colsize = CS
                
        self.cand = [[]] * self.size
        self.cmap = [0 if self.puz[i]=='.' else 1 for i in range(self.size)]
                
        self.iterations = 0
        self.itpermincnt = 0
        self.itpermin = 0
        self.count = 0
        self.solnr = 0
        self.last_solved_puz = None
       
        self.nofields = board.get('nofields', False)
        self.init_data(
            board['fields'],
            self.nofields, 
            board.get('efields'),
            board.get('oddeven'))
       
        self.init_calc(board.get('calc')) 
        self.init_edges()
        cnt = self.get_candidates(init=True)
        print ("Initial candidates %d" %(cnt)) 
        

    def guess_digits(self, puz):
        """
        find best matching set of digits from the given digits
        If that doesn't work you need to pass the digits in the board['digits']
        """
        result = []
        digitset = []
        digitset.append([str(i+1) for i in range(CS)])
        digitset.append([str(i) for i in range(CS)])
        digitset.append(['%X'%(i) for i in range(CS)])
        digitset.append(['%x'%(i) for i in range(CS)])
        score = 0
        for digits in digitset:
            sc = len(set(digits).intersection(puz))
            if sc>score:
                score = sc 
                result = digits
        if len(result) == 0:
            result = digitset[0]
        return result
        
    def init_data(self, fields, nofields, efields, oddeven):
        """
        initialize internal data structures
        """
        # setup index tables for rows, columns and fields
        self.r_ind = [set([i for i in range(r*RS, r*RS+CS)]) for r in range(RS)]
        self.c_ind = [set([i for i in range(c, self.size, CS)]) for c in range(CS)]
        self.f_ind = []
        self.cellind = [] # to know to with row, column and field a cell belongs
        self.cellvis = [] # index table for all visible cell indexes, per cell
        
        if fields is None:
            self.fields = []
            if not nofields:
                # regular square fields
                self.fields=[0] * self.size
                field = 0
                SS = int(sqrt(RS))
                for r in range(0,RS,SS):
                    for c in range(0,CS,SS):
                        field_indices = set([(i*CS)+j for i in range(r, r+SS) for j in range(c, c+SS)])
                        for i in field_indices:
                            self.fields[i] = [field]
                        field += 1
        else:
            # irregular fields
            self.fields = []
            for item in fields:
                if type(item) == list: 
                    self.fields.extend(item)
                else:
                    self.fields.append(item)

        # re-index self.fields (convert to integer indices)
        # populate self.f_ind     
        field_names = []
        for f in self.fields:
            if not f in field_names:
                field_names.append(f)
        field_names.sort()
        
        self.f_ind = [set() for _ in range(len(field_names))]
        for i, f in enumerate(self.fields):
            fn = field_names.index(f)
            self.fields[i] = [fn]
            self.f_ind[fn].add(i)

        self.digitsets = {}
        self.oddeven = ['.'] * self.size if oddeven is None else oddeven
        
        # For odd/even fields and calcudokus we need the integer representation of the (string) digits
        if 'A' in self.digits:
            self.numdigits = sorted([int(d, 16) for d in self.digits]) 
        else:
            self.numdigits = sorted([int(d, 10) for d in self.digits]) 
            
        for ch in set(self.oddeven):
            if   ch == '.': 
                self.digitsets[ch] = self.digits
                print ('Digits:      %s' %(','.join(self.digitsets[ch])))
            elif ch == 'O': 
                self.digitsets[ch] = [self.digits[self.numdigits.index(d)] for d in self.numdigits if int(d)%2 == 1]
                print ('Odd digits:  %s%s%s' %(oddevencolors[ch], ','.join(self.digitsets[ch]), normal))
            elif ch == 'E': 
                self.digitsets[ch] = [self.digits[self.numdigits.index(d)] for d in self.numdigits if int(d)%2 == 0]
                print ('Even digits: %s%s%s' %(oddevencolors[ch], ','.join(self.digitsets[ch]), normal))
            else: 
                raise ValueError("Unknown oddeven specifier '%s', should be 'O', 'E' or '.'  " %(ch))
        print()
                

        if efields is not None:
            efnr = len(self.f_ind)
            for efield in efields:
                field_indices = set()
                for i, f in enumerate(efield):
                    if f != '.':
                        field_indices.add(i)
                        self.fields[i].append(efnr)
                self.f_ind.append(field_indices)
                efnr += 1

        for i in range(self.size):
            row, col = self.coord(i)
            fields = [] if nofields else self.fields[i] 
            self.cellind.append([row, col, fields])
            
            row_list = [j for j in self.r_ind[row]]
            col_list = [j for j in self.c_ind[col]]
            fld_list = []
            for field in fields:
                fld_list.extend([j for j in self.f_ind[field]])
            self.cellvis.append(set(row_list+col_list+fld_list))

    def init_calc(self, calc):
        """
        Not implemented here
        """
        pass
        
    def init_edges(self):
        """
        Construct the frame and field edges of the puzzle for printing
        To be overridden by sub classes 
        """
        RS = self.rowsize
        CS = self.colsize
        
        # construct self.frame for print_puzzle()
        self.frame = []
        for r in range(RS):
            vline, hline = '', ''
            lastf = 0
            for c in range(CS):
                i = self.indexof(r,c)
                
                if r==0:
                    h = '+---'
                elif self.nofields:
                    h = '+   '
                else:     
                    f =self.fields[i]
                    # field color logic
                    fu = self.fields[i-CS] # field 1 up
                    fur = self.fields[i-CS+1] if c<(CS-1) else [0] # field 1 up, right
                    fr = self.fields[i+1] if c<(CS-1) else [0] # field 1 right
                    
                    h = '---' if f[0] != fu[0] else '   '
                    n, col = '', ''
                    if any(_f in fu for _f in f[1:]):
                        if lastf!=f[1]: lastf, n, col = f[1], normal, efieldcolors[f[1]%2]
                    elif any(_f in fur for _f in f[1:]):
                        h=h+'%d' %(f[1]%2) if f[1] in fur else h+'%d' %(fur[1]%2)
                    elif any(_f in fu for _f in fr[1:]):
                        h=h+'%d' %(fr[1]%2) if fr[1] in fu else h+'%d' %(fu[1]%2)
                    elif lastf > 0:
                        lastf, n = 0, normal
                    h = n +'+' + col + h
                hline += h
                
                if c==0:
                    v = '|'
                elif self.nofields:
                    v = ' '
                else:
                    f =self.fields[i]
                    f2 = self.fields[i-1]
                    v = '|' if f[0] != f2[0] else ' '
                    if len(f)>1 and len(f2)>1 and f[1] == f2[1]:
                        v = efieldcolors[f[1]%2] + v + normal
                vline += v + '%s'
            
            while 1:
                # diagonal coloring
                match = re.match('(.+?)([\- ])([01])(.{2})(.+)', hline)
                if match is None:
                    break
                m1, m2, num, m3, m4 = match.groups()
                if m3[0] == '+' and m3[1] in (' ','-'):
                    hline = m1 + efieldcolors[int(num)] + m2 + m3 + normal + m4
                else:
                    hline = m1 + m2 + m3 + m4
                    
              
            self.frame.append(hline + normal + '+')
            self.frame.append(vline + '|')
        self.frame.append('+---'*RS + '+')

        # construct self.cframe for print_candidates()
        self.cframe = deepcopy(self.frame)
        for i, line in enumerate(self.cframe):
            if i == 0:
                ll = line.split('+')
                for c in range(CS):
                    ll[c+1] =  '%6d    ' %(c+1)
                line = '+'.join(ll)
                self.cframe[i] = '  '+line.replace(' ', '-')
            elif '+' in line:
                line = line.replace(' +', '        +')
                line = line.replace('-+', '--------+')
                line = line.replace(' '+normal+'+', '        '+normal+'+')
                line = line.replace('-'+normal+'+', '--------'+normal+'+')
                self.cframe[i] = '  '+line
            else:
                self.cframe[i] = '%-2d'%(1+i//2) + line
        
        self.cursorup = '\033[%dA' %(2+len(self.frame))

        
    def mark_uncertain_cells(self, p1, p2, cmap):
        for i in range(self.size):
            if p1[i] != p2[i]:
                cmap[i] = 3 

    def cmap_replace(self, cmap, val1, val2):
        """
        Replace val1 in cmap to val2
        """
        for i in range(self.size):
            if cmap[i] == val1:
                cmap[i] = val2


    def coord(self,i):
        col = i%CS
        row = i//CS
        return (row, col,)

        
    def indexof(self, row, col):
        return (row*CS) + col

    def cell_info(self,i):
        """
        Internally the row and column indexes are 0-based
        For printing purpose we convert to 1-base
        """
        r,c = self.coord(i)
        return "r%d/c%d" %(r+1,c+1)

    def eliminate_digits(self, i, digits, cmap, markcolor=6):
        self.cand[i] = [d for d in self.cand[i] if d not in digits]
        cmap[i] = markcolor
        return -1, 0
    
    def fix_digit(self, i, digit, markcolor=2):
        """
        Mark a solution in self.puz and place the color mark
        Also the candidates can be cleaned here
        """
        self.puz[i] = digit
        self.cmap[i] = markcolor
        self.cand[i] = [digit]
        
        return -1, -1

    def print_puzzle(self, cmap=None, overwrite=False, info=''):
        """
        An attempt to print a sudoku board using ASCII art
        You can override it in a subclass
        """
        RS = self.rowsize
        CS = self.colsize
        if overwrite:
            print (self.cursorup, end='')
        if cmap is None:
            cmap = self.cmap
        print ('  ' + self.name)
        
        ln = 0
        i = 0
        for _ in range(RS):
            print (self.frame[ln])
            ln += 1
            cells = []
            for _ in range(CS):
                ccolor = color[cmap[i]]
                fcolor = ''
                if self.nofields == False and len(self.fields[i])>1:
                    fldnr = self.fields[i][1] 
                    fcolor = efieldcolors[fldnr%2]
                if self.oddeven[i] != '.':
                    fcolor = oddevencolors[self.oddeven[i]]
                cells.append(fcolor + ccolor + "%2s " %(self.puz[i]) + normal)
                i += 1    
            print (self.frame[ln] % tuple(cells))
            ln += 1
        print (self.frame[ln])
        print ('  ' + info)
        

    def print_candidates(self, cmap=None, info=''):
        """
        Shows the candidates of each cell
        """
        RS = self.rowsize
        CS = self.colsize
        if cmap is None:
            cmap = self.cmap
        print ('  ' + self.name)
       
        ln = 0
        i = 0
        for _ in range(RS):
            print (self.cframe[ln])
            ln += 1
            cells = []
            for _ in range(CS):
                digits = ''.join(self.cand[i])
                ccolor = color[cmap[i]]
                fcolor = ''
                if self.nofields == False and len(self.fields[i])>1:
                    fldnr = self.fields[i][1] 
                    fcolor = efieldcolors[fldnr%2]
                if self.oddeven[i] != '.':
                    fcolor = oddevencolors[self.oddeven[i]]
                    
                cells.append(fcolor + ccolor + "%10s" %(digits) + normal)
                i += 1    
            print (self.cframe[ln] % tuple(cells))
            ln += 1
        print (self.cframe[ln])
        print ('  ' + info)


    def find_unique_positions(self, s):
        """
        let s be a set of indices, then find the candidates that only occur once
        returns a dict where key is a digit and value the index where it was found 
        """
        result = {}
        ccount = {}
        for i in s:
            for c in self.cand[i]:
                if c in ccount: 
                    ccount[c].append(i)
                else:
                    ccount[c] = [i]
        for digit, pos in ccount.items():
            if len(pos) == 1:
                result[digit] = pos[0]
        
        return result

    
    def find_digits(self, i):
        """
        find which digits can be placed at index i 
        """
        #if DEBUG: print ('%d:' % i, end='')
       
        digitset = set(self.digitsets[self.oddeven[i]]) 
        values = [self.puz[j] for j in self.cellvis[i] ]
        result = digitset.difference(values)
        #if DEBUG: print (result)

        return result


    def find_empty_cell(self):
        try:
            return self.puz.index('.')
        except:
            return None


    def solved(self):
        return self.find_empty_cell() is None
 
 
    def bruteforce(self):
        """
        Recursive function 
        """
        global t
        
        i = self.find_empty_cell()
        if i is None:
            return True
           
        self.iterations += 1
        self.itpermincnt += 1
        self.count += 1
        if self.count > 100000:
            info = "%d iterations (%d per min)" %(self.iterations, self.itpermin)
            self.print_puzzle(overwrite=True, info=info)
            self.count = 0
        if time.time() > t+60:
            t=time.time()
            self.itpermin = self.itpermincnt
            self.itpermincnt = 0
        
        options = self.find_digits(i)
        for digit in self.cand[i]:
            if digit in options:
                self.puz[i] = digit

                if self.bruteforce():
                    #### to find the fist solution only:
                    #return True
                    ####
                    if self.last_solved_puz is not None:
                        self.mark_uncertain_cells(self.last_solved_puz, self.puz, self.cmap)
                    self.last_solved_puz = deepcopy(self.puz)    
                    self.solnr += 1 
                    info="possible solution %d, %d iterations" %(self.solnr, self.iterations)
                    self.print_puzzle(overwrite=True, info=info)
                    print()
                    self.print_puzzle()

                self.puz[i] = '.'

        return False


    def get_candidates(self, s=None, init=False, verbose=False, handle_postponed=False):
        """
        Populate the candidate data by simple inspection
        Operates on the cell indices in s if given, else on all cells
        """

        if s is None:
            s = range(self.size)
        
        cand_cnt = 0
        for i in s:
            if self.puz[i] == '.':
               
                possible_digits =  self.find_digits(i)
                digits = list(possible_digits) if init else list(possible_digits & set(self.cand[i]))
                
                if len(digits) == 0:
                    raise ValueError('No candidates found for %s' %self.cell_info(i))
                
                if len(digits) != len(self.cand[i]):
                    self.cand[i] = sorted(digits, key=lambda d: self.digits.index(d))
                    cand_cnt += len(self.cand[i])
            else:
                self.cand[i] = [self.puz[i]]
        return cand_cnt
    

    def prune_candidates(self, markcolor=2, cmap=None, verbose=None):
        """
        - find digits that are needed for a field and appear on the same row/col
          then, remove the digit from row/col in other fields 
        - find digits that are needed for a row/col and appear in the same field
          then, remove the digit from fields in other row/col
        """

        if cmap is None: cmap = self.cmap
        if verbose is None: verbose = VERBOSE
       
        if verbose > 0: print ('\nprune candidates', self.name)
        updates = 0
        # investigate fields
        for field, fieldset in enumerate(self.f_ind):
            digit_r, digit_c = {}, {}
            for digit in self.digits:
                digit_r[digit], digit_c[digit] = [], []
                for i in fieldset:
                    row, col, _ = self.cellind[i]
                    if digit in self.cand[i]:
                        digit_r[digit].append(row)
                        digit_c[digit].append(col)
                
            for digit in digit_r:
                zr, zc = list(set(digit_r[digit])), list(set(digit_c[digit]))
                if len(zr)==1 and len(zc)>1:
                    row = zr[0]
                    for i in self.r_ind[row]:
                        r, c, flds = self.cellind[i]
                        if field not in flds and digit in self.cand[i]:
                            self.eliminate_digits(i, [digit], cmap)
                            updates += 1
                            if verbose > 0: print("* remove %s from row %d, outside field %d: %s @ %s" %
                                  (digit, r+1, field+1, digit, self.cell_info(i)) )
                if len(zr)>1 and len(zc)==1:
                    col = zc[0]
                    for i in self.c_ind[col]:
                        r, c, flds = self.cellind[i]
                        if field not in flds and digit in self.cand[i]:
                            self.eliminate_digits(i, [digit], cmap)
                            updates += 1
                            if verbose > 0: print("* remove %s from col %d, outside field %d: %s @ %s" %
                                  (digit, c+1, field+1, digit, self.cell_info(i)) )


        # investigate rows
        if len(self.f_ind) > 0:
            for row, rowset in enumerate(self.r_ind):
                #print ('Check row', row)
                digit_f = {}
                for digit in self.digits:
                    digit_f[digit] = []
                    
                    for i in rowset:
                        _, _, flds = self.cellind[i]
                        if digit in self.cand[i]:
                            digit_f[digit].extend(flds)
                    
                for digit in digit_f:
                    fields = list(set(digit_f[digit]))
                    if len(fields)==1 and len(digit_f[digit])>1:
                        field = fields[0]
                        for i in self.f_ind[field]:
                            r, c, _ = self.cellind[i]
                            if row != r and digit in self.cand[i]:
                                self.eliminate_digits(i, [digit], cmap)
                                updates += 1
                                if verbose > 0: print("* remove %s from field %d, not in row %d: %s @ %s" %
                                      (digit, field+1, row+1, digit, self.cell_info(i)) )
                                        
            # investigate columns
            for col, colset in enumerate(self.c_ind):
                #print ('Check col', col)
                digit_f = {}
                for digit in self.digits:
                    digit_f[digit] = []
                    
                    for i in colset:
                        _, _, flds = self.cellind[i]
                        if digit in self.cand[i]:
                            digit_f[digit].extend(flds)
                    
                for digit in digit_f:
                    fields = list(set(digit_f[digit]))
                    if len(fields)==1 and len(digit_f[digit])>1:
                        field = fields[0]
                        for i in self.f_ind[field]:
                            r, c, _ = self.cellind[i]
                            if col != c and digit in self.cand[i]:
                                self.eliminate_digits(i, [digit], cmap)
                                updates += 1
                                if verbose > 0: print("* remove %s from field %d, not in col %d: %s @ %s" %
                                      (digit, field+1, col+1, digit, self.cell_info(i)) )

        

        return updates 


    def find_solutions(self, markcolor=2, cmap=None, verbose=None):
        """
        find cells that have only 1 candidate
        find digits in rows which can only be placed in one position
        find digits in columns which can only be placed in one position
        find digits in fields which can only be placed in one position
        """
        if cmap is None: cmap = self.cmap
        if verbose is None: verbose = VERBOSE
        
        if verbose > 0: print ('\nfind solutions for', self.name)
        updates = 0
        
        # find cells that have only 1 candidate
        for i in range(self.size):
            if self.puz[i] == '.' and len(self.cand[i]) == 1:
                digit = self.cand[i][0]
                options = self.find_digits(i)
                if digit not in options:
                    raise ValueError('Inconsistency at %s, %s is not in %s' %(self.cell_info(i), digit, options))
                self.fix_digit(i, digit, markcolor)
                updates += 1
                if verbose > 0: print ("* Found solution in %s: single candidate %s" %(self.cell_info(i), digit))
                    
        # find digits in rows which can only be placed in one position
        for row, rowset in enumerate(self.r_ind):
            solutions = self.find_unique_positions(rowset)
            for digit,i in solutions.items():
                if  self.puz[i] == '.':
                    options = self.find_digits(i)
                    if digit not in options:
                        raise ValueError('Inconsistency at %s, %s is not in %s' %(self.cell_info(i), digit, options))
                    self.fix_digit(i, digit, markcolor)
                    updates += 1
                    if verbose > 0: print ('* Found solution in row %d, pos %s: digit %s' %(row+1, self.cell_info(i), digit))
        
        # find digits in columns which can only be placed in one position
        for col, colset in enumerate(self.c_ind):
            solutions = self.find_unique_positions(colset)
            for digit,i in solutions.items():
                if  self.puz[i] == '.':
                    options = self.find_digits(i)
                    if digit not in options:
                        raise ValueError('Inconsistency at %s, %s is not in %s' %(self.cell_info(i), digit, options))
                    self.fix_digit(i, digit, markcolor)
                    updates += 1
                    if verbose > 0: print ('* Found solution in col %d: pos %s: digit %s' %(col+1, self.cell_info(i), digit))
        
        # find digits in fields which can only be placed in one position
        for field, fieldset in enumerate(self.f_ind):
            solutions = self.find_unique_positions(fieldset)
            for digit,i in solutions.items():
                if  self.puz[i] == '.':
                    options = self.find_digits(i)
                    if digit not in options:
                        raise ValueError('Inconsistency at %s, %s is not in %s' %(self.cell_info(i), digit, options))
                    self.fix_digit(i, digit, markcolor)
                    updates += 1
                    if verbose > 0: print ('* Found solution in field %d: pos %s: digit %s' %(field+1, self.cell_info(i), digit))

        return updates


    def solver(self, markcolor=2, cmap=None, verbose=None):
        """
        
        """
        if verbose is None: verbose = VERBOSE
        updates = 0
        loop = 0
        
        while 1:
            upd = 0
            cand = self.get_candidates()
            if verbose>2: self.print_candidates(info='candidates after get_candidates()')
            
            pruned = self.prune_candidates(verbose=verbose)
            if verbose>2 and pruned>0: self.print_candidates(info='candidates after prune_candidates()')
            
            solved = self.find_solutions(markcolor=markcolor, cmap=cmap, verbose=verbose)

            if verbose>0:
                print ("Solver iteration %d: candidates %d, pruned %d, solved %d" %(loop, cand, pruned, solved))
                print()
                self.print_puzzle()
                print()
            upd += solved
            updates += solved
            if upd == 0:
                break
            loop += 1
        return updates


    def get_path(self, flavor=0):
        if self.walk is None:
            self.walk = []
            if flavor==0:
                # columns and rows 
                for r in range(self.rowsize):
                    l = self.rowsize//2 
                    indr = sorted(list(self.r_ind[r]))
                    for indexlist in [indr[:l], indr[l:]]: 
                    #for indexlist in [indr]: 
                        self.walk.append({'seen': False, 'avg':0, 'indexlist':indexlist})
                for c in range(self.colsize):
                    l = self.colsize//2 
                    indc = sorted(list(self.c_ind[c]))
                    for indexlist in [indc[:l], indc[l:]]: 
                    #for indexlist in [indc]: 
                        self.walk.append({'seen': False, 'avg':0, 'indexlist':indexlist})
            #else:
                # cross hatch pattern
                for _c in range(CS//2, CS):
                    r, c = 0, _c
                    ind1, ind2 = [], []
                    while c >= 0:
                        ind1.append(self.indexof(r, c))
                        ind2.append(self.indexof(RS-r-1, c))
                        r, c = r+1, c-1
                    l = len(ind1)//2
                    for indexlist in [ind1[:l], ind1[l:], ind2[:l], ind2[l:]]: 
                    #for indexlist in [ind1, ind2]: 
                        self.walk.append({'seen': False, 'avg':0, 'indexlist':indexlist})
                
                for _r in range(1, (RS+1)//2):
                    r, c = _r, CS-1
                    ind1, ind2 = [], []
                    while r < RS:
                        ind1.append(self.indexof(r, c))
                        ind2.append(self.indexof(RS-r-1, c))
                        r, c = r+1, c-1
                    l = len(ind1)//2
                    for indexlist in [ind1[:l], ind1[l:], ind2[:l], ind2[l:]]: 
                    #for indexlist in [ind1, ind2]: 
                        self.walk.append({'seen': False, 'avg':0, 'indexlist':indexlist})
          
        sel = -1
        least = -1
        for p, path in enumerate(self.walk):
            cands = 0
            for i in path['indexlist']:
                c = len(self.cand[i])
                cands += c 
            path['avg'] = cands / len(path['indexlist'])
            if (least<0 or path['avg']<least) and not path['seen']:
                least = path['avg'] 
                sel = p
           
        if sel >= 0:
            self.walk[sel]['seen'] = True
            result = self.walk[sel]['indexlist']
        else:
            for path in self.walk: path['seen'] = False
            result = []
            
        return result

    def deepdive(self, verbose=None):
        '''
        This is basically a guessing algorithm, but a smart one:
        
        - Walk over the cells in a pattern optimized for least candidates and try each candidate using the solver.
        - Candidates that cause an exception can be eliminated and reduce the solution space.
        - When the solver finds solutions, try to merge the solutions of the tried candidates in the same cell.
          Solutions that survive the merge can then be fixed as solved.
        '''
        if verbose is None: verbose = VERBOSE
        solved = 0

        if self.solved():
            return solved
        
        iteration = 0
        self.walk = None
        
        while 1: # walk the walks
            updates = 0
            index_list = self.get_path() 
            if len(index_list) > 0 and all(len(self.cand[i]) == 1 for i in index_list):
                # noting to solve for this walk
                continue
            iteration += 1
            
            for i in index_list:
                b_copy = None
                if len(self.cand[i]) == 1:
                    continue
                if len(self.cand[i]) == 0:
                    print ("ERROR: puzzle is inconsistent at %s" %(self.cell_info(i)))
                    break
                cmap_tmp = deepcopy(self.cmap)
                last_puz = None
                upd = 0
                candidates = deepcopy(self.cand[i])
                possible_digits = []
                for digit in candidates:
                    if verbose > 1: 
                        print ("\ndeepdive: trying %s from %s" %(digit, ','.join(self.cand[i])))
                        if not set(self.cand[i]).issubset(candidates):
                            print ('WARN: candidates list is dirty, please fix...')
                    if not digit in self.cand[i]:
                        if verbose: print ('WARN: %s is no more a candidate, it was removed in the meantime' % digit)
                        continue 
                    
                    # NOTE: the deepcopy of the class may be an expensive operation when it has large data tables
                    b_copy = deepcopy(self)
                    info = "deepdive - trying %s@%s" %(digit, b_copy.cell_info(i))    
                    try:
                        b_copy.fix_digit(i, digit, 5)
                        b_copy.solver(markcolor=4, verbose=verbose-2)
                    except ValueError as e:
                        if verbose in (1,2): b_copy.print_puzzle(info=info)
                        if verbose > 1:      print ("%s cannot be in %s: %s" %(digit, b_copy.cell_info(i), str(e)))

                        try:
                            n_old, n_new = self.eliminate_digits(i, [digit], self.cmap)
                            if verbose > 1: 
                                if n_old != -1:
                                    print("Eliminated %s from %s, list size %d -> %d" %(digit, b_copy.cell_info(i), n_old, n_new))
                                else: 
                                    print()
                        except Exception as e2:
                            print (e2)
                                 
                        continue
                    if verbose in (1,2): b_copy.print_puzzle(info=info)
                    if verbose > 1:      print ('\n')

                    # Compare the solutions with previous runs
                    if last_puz is not None:
                        self.mark_uncertain_cells(last_puz, b_copy.puz, cmap_tmp)
                    last_puz = deepcopy(b_copy.puz)    
                    possible_digits.append(digit)
                    
                    #### Take care: this breaks the loop on the first possible solution but that may not the only one (!)
                    #if b_copy.solved():
                    #    possible_digits = [digit] # and forget the rest ...
                    #    cmap_tmp = deepcopy(self.cmap)
                    #    break

                # Find stable cells
                if last_puz is not None:
                    info = 'deepdive: merge solutions of placed digit(s) %s'%(','.join(possible_digits))
                    for i in range(self.size):
                        if cmap_tmp[i] == 0 and last_puz[i] != '.' and self.puz[i] == '.':
                            digit = last_puz[i]
                            if verbose > 0: print (" * iteration %d, found %s; '%s'" %(iteration, self.cell_info(i), digit))
                            self.fix_digit(i, digit, 4)
                            upd += 1
                else:
                    print('BUG! TODO handle case when last_puz is None')
                                
                updates += upd
                if upd>0:
                    s = self.solver(markcolor=4, verbose=verbose-2)
                    updates += s
                    if s > 0: 
                        print ('Deduction found', s)
                        print()
                    if verbose in (1,2): self.print_puzzle(info=info)
                    self.get_candidates(verbose=verbose>1, handle_postponed=True)
                self.cmap_replace(self.cmap, 4, 2)
                self.cmap_replace(self.cmap, 6, 0)
                    
            solved += updates
            print ("deepdive iterations %d solutions %d"%(iteration, updates))            
           
            if self.solved():
                break 
            if len (index_list) == 0: 
                if updates == 0:
                    break

        print ("deepdive updated %d cells in %d iterations" %(solved, iteration))
        return solved

