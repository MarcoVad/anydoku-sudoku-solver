'''
Created on 13 dec. 2022

@author: marco
'''
import os
import json
from pathlib import Path
from Sudoku import SudokuBoard, CalcudokuBoard, HexadokuCBoard 

class BoardReaderError(Exception):
    pass

boards = []

# map type string to tuple: Board class, default rowsize. default columnsize
typemap = {
    'Sudoku':       (SudokuBoard.SudokuBoard, 9, 9),
    'HexadokuC':    (HexadokuCBoard.HexadokuCBoard, 16, 16),
    'Jigsawdoku':   (SudokuBoard.SudokuBoard, 9, 9),
    'Calcudoku':    (CalcudokuBoard.CalcudokuBoard, 9, 9),
    }

def get_fields(fields):
    """
    Get single digit or comma separated field notation from json file
    Returns a one-dimensional list of string values
    """
    if ',' in fields[0]:
        res = [line.replace(' ','').split(',') for line in fields]
    else:
        res = [[digit for digit in line.replace(' ','')] for line in fields]
        
    result = []
    for item in res:
        if type(item) == list: 
            result.extend(item)
        else:
            result.append(item)
    return result
    

def read_from_string(data, conf):
    try:
        data = json.loads(data)
    except Exception as e:
        raise BoardReaderError(e)
    
    if 'name' in data:
        print (data['name'])
    
    if 'comment' in data:
        print (data['comment'])
    
    link = data.get('link')
    
    if link is not None:
        #print ('pwd ' + os.path.abspath(os.path.curdir))
        for lnk in [link, os.path.join('images', link)]:
            if os.path.isfile(lnk) and not os.path.isabs(lnk):
                link = os.path.abspath(lnk)
                break
        if os.path.isabs(link):
            link = Path(link).as_uri()
            
        print ("link: " + link)
        
    print()
    
    for m, board in enumerate(data['boards']):
        # ------------- basic board setup --------- #
        brd = {}
        default_type = 'Sudoku'
        name = board.get('name', 'board%d'%(m+1))
        if 'name' in data:
            name = data['name'] + '.' + name
        brd['name'] = name
        
        boardObj, RS_def, CS_def = typemap[board.get('type', default_type)]
        RS = board.get('rowSize', RS_def)
        CS = board.get('colSize', CS_def)
        brd['fields'] = None 
        brd['nofields'] = board.get('nofields', False)
        
        if 'fields' in board and not brd['nofields']:
            brd['fields'] = get_fields(board['fields'])

        # ------------- odd/even  ---------------- #
        for key, flddata in board.get('oddeven', {}).items():
            if key == 'fields':
                brd['oddeven'] = get_fields(flddata)
            elif key == 'checker_odd' and flddata:
                brd['oddeven'] = [''] * (RS*CS)
                for i in range(RS*CS):
                    c, r = i%CS, i//CS    
                    brd['oddeven'][i] = 'O' if (r+c)%2==0 else 'E'
            elif key == 'checker_even' and flddata:
                brd['oddeven'] = [''] * (RS*CS)
                for i in range(RS*CS):
                    c, r = i%CS, i//CS    
                    brd['oddeven'][i] = 'E' if (r+c)%2==0 else 'O'
            else:
                raise BoardReaderError('key oddeven.%s not supported' %(key))
           
            
        # ---------- extra fields / diagonal  ---------------- #
        
        for key, flddata in board.get('extrafields', {}).items():
            brd['efields'] = []
            if 'diag' in key and flddata == True:
                diag1 = ['1' if (r==c) else '.' for r in range(RS) for c in range(CS)]
                diag2 = ['1' if (r==CS-c-1) else '.' for r in range(RS) for c in range(CS)]
                brd['efields'].append(''.join(diag1))
                brd['efields'].append(''.join(diag2))
            elif key == 'fields':
                layouts = []
                # fields can be a list of strings (for 1 field layout)  or a list of lists of strings (multiple field layouts) ...
                if type(flddata[0]) == str:
                    layouts.append(flddata)
                elif type(flddata[0]) == list:
                    layouts.extend(flddata)
                else:
                    raise BoardReaderError("Don't know what to do with %s", flddata)
                
                for layout in layouts:
                    layout = ''.join(layout)
                    digits = set(layout)
                    digits.discard('.')
                    for digit in sorted(list(digits)):
                        singlefield = [d if d==digit else '.' for d in layout]
                        brd['efields'].append(''.join(singlefield))
            else:
                raise BoardReaderError("Hey, where are the extra fields??")

        # ------------ edge constraints ----------------- #
        for key, edgedata in board.get('edges', {}).items():
            if 'greater' in key:
                gt = [[] for i in range(RS*CS)]
                r = 0
                dots = [c for c,x in enumerate(edgedata[0]) if x=='.']
                for line in edgedata:
                    if '.' in line:
                        for col, op in enumerate(line.split('.')[1:-1]):
                            if op == ' ' : continue
                            i = r*CS + col
                            i2 = i+1
                            gt[i].append((op, i2))
                            gt[i2].append(('<' if op == '>' else '>', i)) # apply inverse operation
                    else:
                        for col, p in enumerate(dots):
                            op = line[p]
                            i = r*CS + col
                            i2 = (r+1)*CS + col
                            if op == 'v':
                                gt[i].append(('>', i2))
                                gt[i2].append(('<', i))
                            elif op == '^':
                                gt[i].append(('<', i2))
                                gt[i2].append(('>', i))
                        r += 1
                brd['gt'] = gt           
                        

        # ----------------- calcudoku ------------------- #
        brd['calc'] = None
        if 'calcufields' in board:
            calcufields = board['calcufields']
            calc = {'layers': [], 
                    'post_rules': calcufields.get('post_rules', []), 
                    'repeat'    : calcufields.get('repeat_digits', True)}
            if 'fields' in calcufields and 'rules' in calcufields:
                layer = {'fields': get_fields(calcufields['fields']),
                         'rules' : calcufields['rules'],
                         'name'  : ''}
                calc['layers'].append(layer)
                
            for key, value in calcufields.items():
                if type(value) == dict:
                    if 'fields' in value and 'rules' in value:
                        layer = {'fields': get_fields(value['fields']),
                                 'rules' : value['rules'],
                                 'name'  : key}
                        calc['layers'].append(layer)
                        
            if len(calc['layers']) == 0:
                raise BoardReaderError("Too bad, calcudoku fields and rules not properly defined...")
                
            brd['calc'] = calc
         
        # ---------------- puzzle grid ------------------ # 
        row, col = board.get('gridRow', 0), board.get('gridCol',0)
        if len(data.get('grid', [])):
            if ',' in data['grid'][0]:
                grid = [line.replace(' ','').split(',') for line in data['grid']]
            else:
                grid = [[digit for digit in line] for line in data['grid']]
            brd['puzzle'] = [grid[i][col:col+CS] for i in range(row, row+RS)]
        else: 
            brd['puzzle'] = ['.' for i in range(RS*CS)]
            
        # ------------- create a board instance ---------- #
        brd['rowsize'] = RS
        brd['colsize'] = CS
        brd['doku'] = boardObj(brd, conf)
        brd['doku'].print_puzzle()
        brd['overlap'] = []
    
        # -------------- overlaps ------------------------ #
        for n, board2 in enumerate(data['boards']):
            if n == m: continue
            row2, col2 = board2['gridRow'], board2['gridCol']
            rows = set(range(row, row+RS)).intersection(set(range(row2,row2+RS)))
            if len(rows) == 0: continue
            cols = set(range(col, col+CS)).intersection(set(range(col2,col2+CS)))
            if len(cols) == 0: continue
            print ('overlaps with', board2.get('name', 'board%d'%(n+1)))
            brd['overlap'].append([
                n, 
                range(min(rows)-row, max(rows)-row+1), row-row2, 
                range(min(cols)-col, max(cols)-col+1), col-col2])

        boards.append(brd)
    return boards    


def read_from_file(filename, conf):
    
    print("AnyDoku - reading file", filename)
    data = open(filename).read()
    return read_from_string(data, conf)

        
        
