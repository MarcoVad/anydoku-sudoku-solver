'''
Created on 4 dec. 2022

@author: marco

Implementation of the Hexadoku with checker board fields.
This is a 4x4 board with hexadecimal digits 0..F.
'''
from Sudoku import SudokuBoard
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
color = [dim, bright, fg_cyan+bright, fg_red, bg_green, blink, bg_magenta]

DIGITS_E = set(['0', '2', '4', '6', '8', 'A', 'C', 'E'])
DIGITS_O = set(['1', '3', '5', '7', '9', 'B', 'D', 'F'])
DIGITS_SET = [DIGITS_E, DIGITS_O]          


class HexadokuCBoard(SudokuBoard.SudokuBoard):
    '''
    Subclass of SudokuBoard.
    Some functions are overridden here to handle specific features (in this case 
    mainly the checker board feature). 
    '''

    def init_edges(self):
        """
        Initialize the horizontal edges for print_puzzle() and print_candidates()
        """
        RS = self.rowsize
        CS = self.colsize
        SS = int(sqrt(RS))
        edge=''   # edge for print_puzzle
        edgec=''  # edge for print_candidates
        edgnc=''  # numbered edge for print_candidates
        for i in range(0,RS,SS):
            for j in range(0,SS):
                edgnc = edgnc+'%6d    ' %(i+j) 
                edgec = edgec+'-'*10
                edge = edge+'-'*3
            edgec = edgec+'+'
            edgnc = edgnc+'+'
            edge = edge+'+'
        self.edgec = ' +' + edgec.replace(' ','-')
        self.edgnc = ' +' + edgnc.replace(' ','-')
        self.edge = '+' + edge.replace(' ','-')
        self.cursorup = '\033[%dA' %(3+CS+SS)


    def print_puzzle(self, cmap=None, overwrite=False, info=''):
        RS = self.rowsize
        CS = self.colsize
        SS = int(sqrt(RS))
        if overwrite:
            print (self.cursorup, end='')
        if cmap is None:
            cmap = self.cmap
        print ('####', self.name, '####')
        print (bg_edge + self.edge + normal )
        i = 0
        for r in range(0,RS):
            print (bg_edge + '|' +normal, end='')
            for c in range(0,CS):
                print (normal, end='')     
                if ((r+c)%2) == 0: print (bg_yellow, end='') 
                print(color[cmap[i]], end='')
                print (" %s " %(self.puz[i]), end='')
                i = i+1
                if c%SS == SS-1:
                    print (normal + bg_edge + '|' + normal, end='')
            print ()
            if r%SS == SS-1:
                print (bg_edge + self.edge + normal )
        print ('  ' + info)

    def print_candidates(self, cmap=None, info=''):
        RS = self.rowsize
        CS = self.colsize
        SS = int(sqrt(RS))
        if cmap is None:
            cmap = self.cmap
        print ('####', self.name, '####')
        print (bg_edge + self.edgnc + normal )
        i = 0
        for r in range(0,RS):
            print (bg_edge + '%2d'%r +normal, end='')
            for c in range(0,CS):
                digits = ''.join(self.cand[i])
                print (normal, end='')     
                if ((r+c)%2) == 0: print (bg_yellow, end='') 
                print(color[cmap[i]], end='')
                i = i+1
                print ("%10s" %(digits), end='')
                if c%SS == SS-1:
                    print (normal + bg_edge + '|' + normal, end='')
            print ()
            if r%SS == SS-1:
                print (bg_edge + self.edgec + normal )
        print ('  ' + info)


    def find_options(self, i):
        """
        find which digits can be placed at index i 
        """
        r, c, _ = self.cellind[i]
        digits = DIGITS_SET[(r+c)%2] # Odd/Even checker board
        values = [self.puz[i] for i in self.cellvis[i] ]
        result = digits.difference(values)

        return result

