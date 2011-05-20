"""
This program compiles SNUSP programs to C.
Copyright (C) 2004, 2009 John Bauman

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
"""

import fileinput

print """#include <stdio.h>
#include <setjmp.h>
#include <stdlib.h>

#ifdef WIN32
#define gtch() getche()
#else
#include <termios.h>
#define gtch() getchar()
#endif

int main(int argc, char **argv) {
int vals[30000] = {0};
int *pvals = vals;
void *envs[10000];
void **penvs = envs;

#ifndef WIN32
struct termios old_tio, new_tio;
/* get the terminal settings for stdin */
tcgetattr(STDIN_FILENO,&old_tio);

/* we want to keep the old setting to restore them at the end */
new_tio=old_tio;

/* disable canonical mode (buffered i/o) */
new_tio.c_lflag &=(~ICANON);
   
/* set the new settings immediately */
tcsetattr(STDIN_FILENO,TCSANOW,&new_tio);
#endif

*(penvs++) = &&endprogram;

goto progstart;
"""


program = []
hasstart = False

for line in fileinput.input():
    if "$" in line:
        hasstart = True

    program.append(list(line))

progwidth = max(len(n) for n in program)

progheight = len(program)

for line in range(len(program)): #pad the lines out
    program[line] += " " * (progwidth - len(program[line]))

skipnum = 0

basicblocks = {}
class BasicBlock:
    def __init__(self, name):
        self.name = name
        self.insts = []
        self.preds = []
        self.succ = None
        self.fakesuccs = []
        self.visitedcount = 0

def addbasicblock(name):
    if name in basicblocks:
        return basicblocks[name]
    else:
        block = BasicBlock(name)
        basicblocks[name] = block
        return block

def outputrowdata(y, row, myname, left, right, realxy):
    """Print out the code for a "row" of data."""
   
    global skipnum
    amskipping = False
    currentbasicblock = None

    if myname == "right" and y == 0 and not hasstart:
        currentbasicblock = addbasicblock("progstart")

    for x, char in enumerate(row):
        xpos, ypos = realxy(x,y)

        if myname == "right" and char == "$":
            newblock = addbasicblock("progstart")
            if currentbasicblock:
                currentbasicblock.succ = newblock
            currentbasicblock = newblock
        if char in "+-><,.":
            if currentbasicblock:
                currentbasicblock.insts.append(char)
        if char == "\\":
            if currentbasicblock:
                currentbasicblock.succ = addbasicblock("%s_%i_%i" % (right, xpos, ypos))
            currentbasicblock = addbasicblock("%s_%i_%i" % (myname, xpos, ypos))
        if char == "/":
            if currentbasicblock:
                currentbasicblock.succ = addbasicblock("%s_%i_%i" % (left, xpos, ypos))
            currentbasicblock = addbasicblock("%s_%i_%i" % (myname, xpos, ypos))
        if char == "?":
            if currentbasicblock:
                succblock = addbasicblock("skip_%i" % skipnum)
                currentbasicblock.fakesuccs.append(succblock)
                currentbasicblock.insts.append("?skip_%i" % skipnum)
        if char == "!":
            if currentbasicblock:
                succblock = addbasicblock("skip_%i" %skipnum)
                currentbasicblock.succ = succblock
                currentbasicblock = None
        if char == "@":
            if currentbasicblock:
                succblock = addbasicblock("skip_%i" % skipnum)
                currentbasicblock.fakesuccs.append(succblock)
                currentbasicblock.insts.append("@skip_%i" % skipnum)
        if char == "#":
            if currentbasicblock:
                currentbasicblock.insts.append("#")
            currentbasicblock = None

        if amskipping:
            newblock = addbasicblock("skip_%i" % (skipnum - 1))
            if currentbasicblock:
                currentbasicblock.succ = newblock
            currentbasicblock = newblock
            amskipping = False 

        if char in "?@!":
            amskipping = True
            skipnum += 1

    #just make sure to clean up - no dangling references
    if amskipping:
        newblock = addbasicblock("skip_%i" % (skipnum - 1))
        if currentbasicblock:
            currentbasicblock.succ = newblock
        currentbasicblock = newblock

    if currentbasicblock:
        currentbasicblock.insts.append("e")



#these parts output the rows of code, forwards and backwards, up and down

for y, row in enumerate(program):
    if "/" in row or "\\" in row or "$" in row or (y == 0 and not hasstart):
        outputrowdata(y, row, "right", "up", "down", 
                      lambda a,b:(a,b))

for y, row in enumerate(program):
    row = row[:]
    row.reverse()
    if "/" in row or "\\" in row:
        outputrowdata(y, row, "left", "down", "up", 
                      lambda a,b:(progwidth - a - 1, b))

for x, row in enumerate(zip(*program)):
    if "/" in row or "\\" in row:
        outputrowdata(x, row, "down", "left", "right", 
                      lambda a,b:(b, a))       

for x, row in enumerate(zip(*program)):
    row = list(row)
    row.reverse()
    if "/" in row or "\\" in row:
        outputrowdata(x, row, "up", "right", "left", 
                      lambda a,b:(b, progheight - a - 1))    

progstart = basicblocks["progstart"]
previsitcount = 0

def dodfs(initial, function):
    global previsitcount
    def actualdfs(item):
        if not item or item.visitedcount > previsitcount:
            return
        item.visitedcount += 1
        function(item)
        actualdfs(item.succ)
        for x in item.fakesuccs:
            actualdfs(x)
    actualdfs(initial)
    previsitcount += 1

#set up the predecessor lists
def optimizedfs(initial):
    if initial.succ:
        initial.succ.preds.append(initial)
    for x in initial.fakesuccs:
        x.preds.append(initial)

dodfs(progstart, optimizedfs)

#combine blocks that lead into each other
def optimize2dfs(initial):
    while initial.succ and initial.succ != initial and len(initial.succ.preds) == 1:
        thissucc = initial.succ
        initial.fakesuccs += thissucc.fakesuccs
        initial.succ = thissucc.succ
        initial.insts += thissucc.insts

dodfs(progstart, optimize2dfs)
def ch1of2(ist, count):
    if count >= 0:
        return ist[0] + str(count)
    return ist[1] + str(-count)
#remove runs of instructions
def optimize3dfs(initial):
    lastinst = ""
    newinsts = []
    count = 0
    for inst in initial.insts:
        if lastinst:
            if lastinst in "+-" and inst not in "+-":
                newinsts.append(ch1of2("+-", count))
                count = 0
            elif lastinst in "><" and inst not in "><":
                newinsts.append(ch1of2("><", count))
                count = 0
            elif lastinst not in "<>+-":
                newinsts.append(lastinst)

        if inst in ">+":
            count += 1
        if inst in "<-":
            count -= 1
        lastinst = inst
    if lastinst:
        if lastinst in "+-":
            newinsts.append(ch1of2("+-", count))
        elif lastinst in "<>":
            newinsts.append(ch1of2("><", count))
        else:
            newinsts.append(lastinst)

    initial.insts = newinsts

dodfs(progstart, optimize3dfs)

def cconvert(inst):
    table = {"+": lambda x:"*pvals += %d;" % int(x or 1),
             "-": lambda x:"*pvals -= %d;" % int(x or 1),
             ">": lambda x:"pvals += %d;" % int(x or 1),
             "<": lambda x:"pvals -= %d;" % int(x or 1),
             ",": "*pvals = gtch();\n" + "if (*pvals == 3) goto endprogram;",
             ".": "putchar(*pvals);",
            #    currentbasicblock.text += 'if (penvs > envs + 9999) goto badpush;\n'
             "@": lambda x: "*(penvs++) = &&%s;" % x,
             "?": lambda x: "if (*pvals == 0) goto %s;" % x,
             "e": "goto endprogram;",
             "#": "goto *(--penvs);"}
    res = table[inst[0:1]]
    if hasattr(res, "__call__"):
        return res(inst[1:])
    return res

#print c code
def printcdfs(initial):
    print initial.name + ":"
    print "".join(cconvert(x) + "\n" for x in initial.insts),
    if initial.succ and initial.succ.visitedcount > previsitcount:
        print "goto " + initial.succ.name + ";"
    print

def printraw(initial):
    print initial.name + ":"
    print "".join(x + "\n" for x in initial.insts),
    if initial.succ and initial.succ.visitedcount > previsitcount:
        print "goto " + initial.succ.name + ";"
    print

dodfs(progstart, printcdfs)

print """
badpush:
printf("Too many @ calls - Ran out of space.");
endprogram:
#ifndef WIN32
tcsetattr(STDIN_FILENO, TCSANOW, &old_tio);
#endif

return 0;
}
"""
