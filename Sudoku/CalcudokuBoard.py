'''
Created on 4 dec. 2022

@author: marco

Subclass of SudokuBoard to extend it for calcudokus
'''
from Sudoku.SudokuBoard import SudokuBoard
from operator import ior, iand
from itertools import permutations
from Sudoku.colors import *
from Sudoku.SudokuBoard import oddevencolors
import re

# color map for cells:
# 0 : empty cell
# 1 : given digit
# 2 : found digit
# 3 : unstable
# 4 : changed cell
# 5 : trying a digit
# 6 : pruned candidates 
color = ['', bg_yellow+bright, fg_cyan+bright, fg_red, bg_green, blink, bg_magenta]

# calc-field, varying background colors
#cfieldcolors = ["\033[48;5;58m", "\033[48;5;59m", "\033[48;5;60m"] 
cfieldcolors = ["\033[48;5;236m", "\033[48;5;237m", "\033[48;5;238m"] 

# to mark digits found for a calc-field, final placement not known yet
cffixcolor = fg_green
postpone_color = bg_yellow 

VERBOSE = True
DEBUG = False

class CalcudokuBoard(SudokuBoard):
    '''
    Subclass of SudokuBoard.
    Some functions are overridden here to handle specific features 
    '''
    MAX_OPTIONS = 1000
    
    def init_calc(self, calc):
        """
        Initialize the data structures for calcudoku types
        """
        
        self.cfields = [[] for _ in range(self.size)]
        self.cfieldlayers = [[] for _ in range(self.size)]
        self.cf_layer_names = []
        self.cf_ind = []
        self.cf_names = []
        self.cf_rules = []
        self.cf_prules = []
        self.cf_options = []
        self.cf_exclusions = set()
        self.cf_fixes = [''] * self.size
       
        for layer in calc['layers']:
            
            cfields = layer['fields']
            cf_rules = layer['rules']
            self.cf_layer_names.append(layer['name']) 
            
            cf_names = sorted(list(set(cfields)))
            if '.' in self.cf_names and '.' in cf_names: cf_names.remove('.')
            self.cf_names.extend([fld_name if fld_name=='.' else fld_name+layer['name'] for fld_name in cf_names])
            
            for name in cf_names:
                self.cf_ind.append([])
                try:
                    # when name is '.', the cell is not a calc field
                    if name == '.':
                        val, op = (0, '.')
                    else:
                        val, op = re.match('(\d+)(.*)', cf_rules[name]).groups()
                except:
                    raise ValueError("ERROR: Calcudoku rule '%s' for field %s not understood" %(cf_rules[name], name)) 
                self.cf_rules.append((int(val), op))
                
            # re-index cfields (convert to integer indices)
            # populate calcudoku lists      
            for i, f in enumerate(cfields):
                # The '.' is special and reserved for normal cells. 
                if f == '.':
                    cfn = self.cf_names.index(f)
                    self.cfieldlayers[i].append(cfn) 
                else:
                    cfn = self.cf_names.index(f+layer['name'])
                    self.cfieldlayers[i].append(cfn) 
                    self.cfields[i].append(cfn)
                    self.cf_ind[cfn].append(i)
                    self.cf_options.append([])
        
        if '.' in self.cf_names:
            cfn = self.cf_names.index('.')
            self.cf_options.append([])
            for i, f in enumerate(self.cfields):
                if len(f) == 0:
                    self.cfields[i].append(cfn)
                    self.cf_ind[cfn].append(i)
            
            
        if not calc['repeat']:
            self.cf_prules.append((0,'u'))  # u for unique, the 0 is a don't care 
        for rule in calc['post_rules']:
            try:
                val, op = re.match('(\d+)(.*)', rule).groups()
                self.cf_prules.append((int(val), op))
            except:
                raise ValueError("ERROR: Calcudoku post rule '%s' not understood" %(rule)) 
    
    def init_edges(self):
        """
        Construct the frame and field edges of the puzzle for printing
        Overridden here for calcudokus
        """
        RS = self.rowsize
        CS = self.colsize
       
        self.frames = []
        self.cframes = []
        for lnum, lname in enumerate(self.cf_layer_names):
            
            # construct self.frame for print_puzzle()
            frame = []
            cframe = []
            for r in range(RS):
                vline, hline = [], []
                for c in range(CS):
                    i = self.indexof(r,c)
                    cf = self.cfieldlayers[i][lnum]
                    hh = '---+'
                    val, op = self.cf_rules[cf]
                    if op != '.' and min(self.cf_ind[cf]) == i:
                        rule = str(val)+op 
                        hh = bright + '%-4s' %(rule[:4]) + normal
                    
                    if r==0:
                        h = hh
                    else: 
                        h = '   '
                        n, col = '', ''
                        
                        # for the square fields
                        if not self.nofields:
                            f =self.fields[i]
                            fu =self.fields[i-CS]
                            h = '---' if f != fu else '   '
                        
                        # field color logic
                        cfu = self.cfieldlayers[i-CS][lnum] # field 1 up
                        if cf == cfu and op != '.':
                            n, col = normal, cfieldcolors[cf%3]
                        
                        if len(hh)>4:
                            h = n + col + hh
                        else:
                            h = col + h + n + '+'
                    hline.append(h)
                    
                    if c==(RS-1):
                        v = '|'
                    else:
                        if self.nofields:
                            v = ' '
                        else:
                            f =self.fields[i]
                            fl = self.fields[i+1]
                            v = '|' if f != fl else ' '
                        
                        cfl = self.cfieldlayers[i+1][lnum]
                        if cf == cfl and op != '.':
                            v = cfieldcolors[cf%3] + v + normal
                    vline.append('%s' + v)
                  
                frame.append('+' + ''.join(hline) + normal)
                frame.append('|' + ''.join(vline))
                
                if r == 0:
                    heading = ['%6d    ' %(c+1) for c in range(CS)]
                    cframe.append('   ' + ' '.join(heading))
                
                exthline = []
                for h in hline:
                    h = h.replace(' +', '        +')
                    h = h.replace('-+', '--------+')
                    hx = h.rfind('\x1b')
                    if hx != -1: h = h[:hx] + '       ' + h[hx:]
                    exthline.append(h)
                        
                cframe.append('  +' + ''.join(exthline) + normal)
                cframe.append('%-2d|'%(r+1)  + ''.join(vline))
                    
            frame.append('+---'*RS + '+')
            cframe.append('  ' + '+----------'*RS + '+')
            self.frames.append(frame)
            self.cframes.append(cframe)

        self.cursorup = '\033[%dA' %(2+len(self.frames[0]))


    def print_puzzle(self, cmap=None, overwrite=False, info=''):
        """
        An attempt to print a sudoku board using ASCII art
        This one supports calcu fields
        """
        RS = self.rowsize
        CS = self.colsize
        if overwrite:
            print (self.cursorup, end='')
        if cmap is None:
            cmap = self.cmap
        print ('  ' + self.name)
        
        for lnum, _ in enumerate(self.cf_layer_names):
            ln = 0
            i = 0
            frame = self.frames[lnum]
            for _ in range(RS):
                print (frame[ln])
                ln += 1
                cells = []
                for _ in range(CS):
                    fldnr = self.cfieldlayers[i][lnum] 
                    cfcolor = '' 
                    if self.cf_names[fldnr]!='.':
                        cfcolor = postpone_color if fldnr in self.cf_exclusions else cfieldcolors[fldnr%3]
                    if self.oddeven[i] != '.':
                        cfcolor = oddevencolors[self.oddeven[i]]
                    if self.puz[i] == '.' and len(self.cf_fixes[i])>0:
                        cell = "%s%2s?" %(cffixcolor , self.cf_fixes[i]) 
                    else:
                        cell = "%s%2s " %(color[cmap[i]] , self.puz[i]) 
                    
                    cells.append(cfcolor + cell  + normal)
                    i += 1    
                print (frame[ln] % tuple(cells))
                ln += 1
            print (frame[ln])
            print ('  ' + info)
        


    def print_candidates(self, cmap=None, info=''):
        """
        An attempt to print a sudoku board using ASCII art
        This one supports calcu fields
        """
        RS = self.rowsize
        CS = self.colsize
        if cmap is None:
            cmap = self.cmap
        print ('  ' + self.name)

        for lnum, _ in enumerate(self.cf_layer_names):
            frame = self.cframes[lnum]

            print (frame[0])
            ln = 1
            i = 0
            for _ in range(RS):
                print (frame[ln])
                ln += 1
                cells = []
                for _ in range(CS):
                    digits = ''.join(self.cand[i])
                    fldnr = self.cfieldlayers[i][lnum] 
                    cfcolor = '' 
                    if self.cf_names[fldnr]!='.':
                        cfcolor = postpone_color if fldnr in self.cf_exclusions else cfieldcolors[fldnr%3]
                    if self.oddeven[i] != '.':
                        cfcolor = oddevencolors[self.oddeven[i]]
                    cells.append(cfcolor + color[cmap[i]] + "%10s" %(digits) + normal)
                    i += 1    
                print (frame[ln] % tuple(cells))
                ln += 1
            print (frame[ln])
        print ('  ' + info)

    def cfield_info(self, i, cfn):
        """
        Internally the calc fields are indexed by number
        For printing purpose we convert to the name given in the input data
        """
        if cfn in self.cf_exclusions:
            return '[%d]' %(len(self.cand[i])) 
        fname = self.cf_names[cfn]
        val, op = self.cf_rules[cfn]
        return '%s:%d%s[%d]' %(fname, val, op, len(self.cf_options[cfn])) 

    def cell_info(self, i):
        """
        Internally the row and column indexes are 0-based
        For printing purpose we convert to 1-base
        """
        r,c = self.coord(i)
        cfield_info = [self.cfield_info(i, cfn) for cfn in self.cfields[i]]
        return "r%d/c%d (%s)" %(r+1, c+1, '/'.join(cfield_info))
        

    def eliminate_digits(self, i, digits, cmap, markcolor=6):
        """
        Check if the cell is part of a calc-field. 
        If so, we can prune the calc-field options which also affects the other cells in the calc-field(s)
        else simply remove the digits from self.cand[i]
        """
        if DEBUG: 
            print('  eliminate_digits %s in %d, %s' %(digits, i, self.cell_info(i)))
            print('  * candidates', ','.join(self.cand[i]))
            for cfn in self.cfields[i]:
                print('  * cfn %d, %s' %(cfn, self.cfield_info(i, cfn)))

        if not any(d in self.cand[i] for d in digits):
            return 0, 0
            
        numdigits = {int(d) for d in digits}
        for cfn in self.cfields[i]:
            
            if cfn in self.cf_exclusions:
                # non-calc fields or postponed calc fields
                old_size = len(self.cand[i])
                self.cand[i] = [d for d in self.cand[i] if d not in digits]
                new_size = len(self.cand[i])
                if old_size != new_size:
                    cmap[i] = markcolor
                    
            else:    
                # calc fields
                old_size = len(self.cf_options[cfn])
                
                cfield = self.cf_ind[cfn]
                k = cfield.index(i)
                numcand = [[int(d) for d in self.cand[cfi]] for cfi in cfield]
                
                new_options = set()
                for option in self.cf_options[cfn]:
                    if option[k] not in numdigits:
                        if len(self.cfields[i])==1 or all(option[m] in numcand[m] for m in range(len(cfield))):
                            new_options.add(option)
             
                new_size = len(new_options)
                if new_size == 0:
                    raise ValueError('No candidates found for %s' %(self.cfield_info(i, cfn)))
                
                # update candidates when calc field options have changed
                if old_size != new_size:
                    self.cf_options[cfn] = new_options
                    for p, ii in enumerate(cfield):
                        old_cand = len(self.cand[ii])
                        self.cand[ii] = sorted(list(set([str(option[p]) for option in new_options])), 
                            key=lambda d: self.digits.index(d))
                        if old_cand != len(self.cand[ii]):
                            cmap[ii] = markcolor
        
        #TODO: sizes are not correct for multiple calc field layers
        return old_size, new_size
        
    
    def fix_digit(self, i, digit, markcolor=2):
        """
        Mark a solution in self.puz and place the color mark
        Also the candidates can be cleaned here
        When the cell is part of a calc-field then remove the invalid calc-field options
        """
        self.puz[i] = digit
        updates = 0
        if DEBUG: print('fix digit %s in %d, %s' %(digit, i, self.cell_info(i)))

        # clean the candidates in the cell itself
        el_cand = [d for d in self.cand[i] if d != digit]
        if el_cand:
            if DEBUG: print('* elim %s in %d, %s' %(','.join(el_cand), i, self.cell_info(i)))
            
            old_size, new_size = self.eliminate_digits(i, el_cand, self.cmap)
            updates += new_size - old_size
        
        # clean the candidates that are visible to the cell
        for ii in self.cellvis[i]:
            if ii != i:
                if DEBUG: print('* elim %s in %d, %s' %(digit, ii, self.cell_info(ii)))
                old_size, new_size = self.eliminate_digits(ii, [digit], self.cmap)
                if old_size != new_size:
                    updates += 1

        self.cmap[i] = markcolor
        
        return updates


    def get_calcfield_options(self, field, rule, postrules, debug=False):
        """
        Get a list of all placement options for the given calc field
        It is assumed that self.cand[] is populated
        This algo is tricky, therefore debug option may be handy 
        """
        
        def check_option(option):
            result = True
            magic = []
            for m, d in enumerate(option):
                #check that permuted options are allowed by digits[m]
                if not d in digits[m]:
                    result = False
                    break
                for x in cell_ind[m]:
                    magic.append(x + d)

            # check for duplicates within rows, columns, fields
            result &= len(magic) == len(set(magic)) 
           
            if result and len(results) > CalcudokuBoard.MAX_OPTIONS:
                raise ValueError('too many options')
            
            if debug:
                print (option, magic, result)
            return result
        
        def loop(option, m=0):
           
            if m<len(field):
                for d in digits[m]:
                    option[m]=d
                    loop(option, m+1)
            else:
                value, operator = rule
                if operator in '/-':
                    options = [sorted(option, reverse=True)]
                elif operator in '%^':
                    options = permutations(option) 
                else:
                    options = [option] 
               
                for option in options:
                    result=option[0]
                    for v in option[1:]:
                        if   operator == '+':      result = result + v
                        elif operator == 'x':      result = result * v
                        elif operator == '/':      result = result / v
                        elif operator == '-':      result = result - v
                        elif operator == '^':      result = result ** v
                        elif operator == '|':      result = ior(result, v)
                        elif operator == '&':      result = iand(result, v)
                        elif operator == '%':      result = result % v
                        elif operator == '':       result = v
                        else: raise ValueError('Caludoku operator %s not implemented' %(operator))
                            
                    # apply post rules if any
                    valid = True
                    for pvalue, poperator in postrules:
                        if    poperator == '%':     result, value = result % value, pvalue
                        elif  poperator == 'u':     valid = len(set(option)) == len(option)
                        else: raise Exception('Caludoku post-operator %s not implemented' %(poperator))
                    
                    if debug:
                        print (option, result==value, valid)
                        
                    if result==value and valid:
                        if operator in '/-^%':
                            for option_p in permutations(option):
                                if check_option(option_p):
                                    results.add(option_p)
                        else:
                            if check_option(option):
                                results.add(tuple(option))
                        break
                    else:
                        invalid[0] += 1
                        if invalid[0] > 1000 * CalcudokuBoard.MAX_OPTIONS:
                            raise ValueError('too many options')
        value, operator = rule
        digits_filter = set(self.numdigits) # start off with all possible digits 
        if operator == 'x':
            digits_filter = set([d for d in digits_filter if (value % d)==0])

        digits = []
        for i in field:
            digits.append( set([int(d) for d in self.cand[i] ]) & digits_filter)
             
        results = set()
        option = [0 for _ in field]
        invalid = [0]
        
        lend = len(self.digits)
        cell_ind = [[]] * len(field)
        for p, i in enumerate(field):
            mult = lend+1
            row, col, flds = self.cellind[i]
            cell_ind[p] = [(row+1) * mult]
            mult *= mult      
            cell_ind[p].append((col+1) * mult)
            for fld in flds:
                mult *= mult      
                cell_ind[p].append((fld+1) * mult)
       
        if debug:
            for d in digits:
                print (d)
            print (rule, cell_ind)
        loop(option)
        #print (' invalid %d' % invalid[0], end='')
        return results


    def get_candidates(self, s=None, init=False, verbose=False, handle_postponed=False):
        """
        Populate the candidate data by inspecting the calcu rules
        Reuses current values in self.cand[]
        """
       
        def update_candidates(cfn, cfield):
            
            val, op = self.cf_rules[cfn]
            fname = self.cf_names[cfn]
            cand_cnt = 0
            CalcudokuBoard.MAX_OPTIONS = self.conf.maxoptions
            
            if verbose: print ('* %s: %-8s\t%d cells' %(fname, str(val)+op, len(cfield)), end='', flush=True)
            try: 
                options = self.get_calcfield_options(cfield, self.cf_rules[cfn], self.cf_prules)
                if verbose: print (' [%d]' %(len(options)))
            except ValueError:
                if verbose: print (' [>%d] \t(postponed)' %(CalcudokuBoard.MAX_OPTIONS))
                self.cf_exclusions.add(cfn)
                return 0
        
            self.cf_options[cfn] = options
              
            if len(options) == 0:
                f_info = '%s:%d%s[%d]' %(fname, val, op, len(options)) 
                raise ValueError('No candidates found for %s' %(f_info))
            
            # populate the candidates per cell
            for p, i in enumerate(cfield):
                self.cand[i] = sorted(list(set([str(option[p]) for option in options])), 
                    key=lambda d: self.digits.index(d))
                
                if self.puz[i] == '.':
                    cand_cnt += len(self.cand[i])
       
            return cand_cnt
        
        cand_cnt = 0
        # needed for init but else not harmful:
        cand_cnt += SudokuBoard.get_candidates(self, init=init)
        
        if init:
            verbose = True
            if verbose: print ('Initialize calcufield options')

            # exclude 'normal' cells from calc field operations
            if '.' in self.cf_names:
                self.cf_exclusions.add(self.cf_names.index('.'))

            for cfn, cfield in enumerate(self.cf_ind):
                if not cfn in self.cf_exclusions:
                    cand_cnt += update_candidates(cfn, cfield)

        else:
            if handle_postponed:
                if verbose: print ('\nInitialize postponed calcufield options')
                for cfn, cfield in enumerate(self.cf_ind):
                    if cfn in self.cf_exclusions and self.cf_names[cfn] != '.':
                        cand_cnt += update_candidates(cfn, cfield)
                        if len(self.cf_options[cfn]) > 0:
                            self.cf_exclusions.remove(cfn)
        
        return cand_cnt

    def prune_candidates(self, markcolor=2, cmap=None, verbose=None):
        """
        - find digits that are needed for a field and appear on the same row/col
          then, remove the digit from row/col in other fields 
        
        For the calcudoku we will do this per calc field. 
        First consider all calc options which can span multiple rows/cols and see which values
         persist over all options
        Then visit the other calc field appearing on the same row or column and eliminate the 
         approriate options if any.
         .
        """
        if cmap is None: cmap = self.cmap
        if verbose is None: verbose = VERBOSE

        if verbose > 0: print ('\nprune candidates in calc fields', self.name)
        
        updates = 0
        for cfn, cfield in enumerate(self.cf_ind):
            val, op = self.cf_rules[cfn]
            fname = self.cf_names[cfn] + ':' + str(val) + op
            if op == '.': continue
            
            rcnt, rcand = {}, {}
            ccnt, ccand = {}, {}
            fcnt, fcand = {}, {}    
                
            # skip field if already completed 
            if all(self.puz[i] != '.' for i in cfield):
                continue
            
            # Break down calc field into rows/cols/fields and containing candidates
            for i in cfield:
                r, c, flist = self.cellind[i]
                if r in rcnt:
                    rcnt[r].append(c)
                    rcand[r].update(self.cand[i])
                else:
                    rcnt[r] = [c]
                    rcand[r] = set(self.cand[i])
                if c in ccnt:
                    ccnt[c].append(r)
                    ccand[c].update(self.cand[i])
                else:
                    ccnt[c] = [r]
                    ccand[c] = set(self.cand[i])
                for f in flist:
                    if f in fcnt:
                        fcnt[f].append(i)
                        fcand[f].update(self.cand[i])
                    else:
                        fcnt[f] = [i]
                        fcand[f] = set(self.cand[i])
                    
            # Find digits per row that are required by the calc field, eliminate elsewhere        
            for row in rcnt:
                cols, cand = rcnt[row], rcand[row]
                if len(cols) == len(cand):
                    info = '* calcfield %s requires %s in row %d' %(fname, ','.join(cand), row+1)
                    lcand = list(cand)
                    
                    for i in self.r_ind[row]:
                        r,c = self.coord(i)
                        if c in cols:
                            self.cf_fixes[i] = lcand.pop()
                            continue
                        
                        # Eliminate in same row but outside the calc field

                        el_cand = list(cand & set(self.cand[i]))
                        if len(el_cand) == 0: continue
                        n_old, n_new = self.eliminate_digits(i, el_cand, cmap)
                        if n_old != n_new:
                            updates += 1
                            if verbose > 0:
                                if len(info) > 0:
                                    print (info)
                                    info = '' 
                                print ('  * Eliminate %s in %s list size %d -> %d' %(','.join(el_cand), self.cell_info(i), n_old, n_new)) 
                        
            # Find digits per column that are required by the calc field, eliminate elsewhere        
            for col in ccnt:
                rows, cand = ccnt[col], ccand[col]
                if len(rows) == len(cand):
                    info = '* calcfield %s requires %s in col %d' %(fname, ','.join(cand), col+1)
                    lcand = list(cand)
                    
                    for i in self.c_ind[col]:
                        r,c = self.coord(i)
                        if r in rows: 
                            self.cf_fixes[i] = lcand.pop()
                            continue
                        
                        # Eliminate in same column but outside the calc field
                        el_cand = list(cand & set(self.cand[i]))
                        if len(el_cand) == 0: continue
                        n_old, n_new = self.eliminate_digits(i, el_cand, cmap)
                        if n_old != n_new:
                            updates += 1
                            if verbose > 0:
                                if len(info) > 0:
                                    print (info)
                                    info = '' 
                                print ('  * Eliminate %s in %s list size %d -> %d' %(','.join(el_cand), self.cell_info(i), n_old, n_new)) 

            # Find digits per field that are required by the calc field, eliminate elsewhere        
            for fld in fcnt:
                cells, cand = fcnt[fld], fcand[fld]
                if len(cells) == len(cand):
                    info = '* calcfield %s requires %s in field %d' %(fname, ','.join(cand), fld)
                    lcand = list(cand)
                    
                    for i in self.f_ind[fld]:
                        if i in cells: 
                            self.cf_fixes[i] = lcand.pop()
                            continue
                        # Eliminate in same field but outside the calc field
                        el_cand = list(cand & set(self.cand[i]))
                        if len(el_cand) == 0: continue
                        n_old, n_new = self.eliminate_digits(i, el_cand, cmap)
                        if n_old != n_new:
                            updates += 1
                            if verbose > 0:
                                if len(info) > 0:
                                    print (info)
                                    info = '' 
                                print ('  * Eliminate %s in %s list size %d -> %d' %(','.join(el_cand), self.cell_info(i), n_old, n_new)) 

         
        pruned = SudokuBoard.prune_candidates(self, markcolor, cmap, verbose)
        updates += pruned
        
        
        return updates
    
    
    
    def bruteforce(self):
        """
        Recursive function 
        """
        print ("Bruteforce is not implemented for calcudokus")
        