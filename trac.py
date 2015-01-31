#! /usr/bin/env python

# trac processor (Mooers' T-64)
# Nat Kuhn (NSK), 7/5/13, v1.0  7/25/13
# 1/1-30/15 NSK with help from BSK, v1.1 implementing meta-sensitive RS with cursor keys

"""
This Trac Processor (i.e., interpreter) implements Calvin N. Mooers Trac T-64 
standard, as described in his 1972 document (RR-284):
http://web.archive.org/web/20050205173449/http://tracfoundation.org/t64tech.htm

There are a few deviations from the Mooers standard, including some 
improvements:

1. In the Mooers standard, the storage primitives (fb,sb,eb) store a "hardware 
address" of the storage block in a named form.  I could have slavishly followed
this, putting the file name in a form, but instead, you just supply the file 
name as the argument, e.g. #(fb,fact.trac)' gets the forms in a file 
"fact.trac" rather than from an address (filename) stored in the form named 
fact.trac

2. I stuck some extra spaces in the trace (#(TN)) output for readability

3. There are a couple extra primitives:

3a.  #(rm,a,b,default) is a "remainder" function, returns a mod b, and the 
default arg for dividing by 0, just as in DV

3b. NI (neutral implied) #(ni,a,b) returns a if the last implied call 
("default call") was neutral.  This allows scripts to function more like true 
primitives.  For example:

#(ds,repeat,(#(eq,*2,0,,(#(ni,#)#(cl,*1)#(cl,repeat,*1,#(su,*2,1))))))'
#(ss,repeat,*1,*2)'
#(ds,a,(#(ps,hello)))'
#(repeat,a,5)'
hellohellohellohellohello
##(repeat,a,5)'
#(ps,hello)#(ps,hello)#(ps,hello)#(ps,hello)#(ps,hello)

NI was described to me by Claude Kagan, and I always thought it was part of 
the T-64 standard, but it's not in the Mooers document cited above.  I have 
no idea whether the idea came from Claude, Mooers, or somewhere else.  
Presumably not from Mooers, because he used the term "default call" while 
Claude used the term "implied call."

4. The "up arrow" (shift-6 on the teletype) was replaced by the caret probably 
in the early 1970s.  I use the caret in PF, though with this new-fangled 
unicode stuff you could probably manage a real up-arrow.  :-/

5. Terminal i/o: #(mo,rt,term-mode) allows you to set the terminal mode to 
a, b, or l.  #(mo,rt) returns the current mode, in lower case.  Incidentally,
'rt' is for 'reactive typewriter,' Mooers' term for an interactive terminal.
    l   line-oriented i/o: uses sys.stdin.readline(), so that you need to 
            hit <enter> before anything is actually read.  Any newline 
            immediately after a meta character is stripped out.
    b   basic terminal: implements a rudimentary backspace, which works back
            to the last newline, and then echoes deleted characters between
            backslashes.  Default mode for Windows, has known issues.  Based 
            on code from Ben Kuhn.
    a   ANSI terminal (e.g., VT-100) mode: default mode for Unix/Mac OS X; 
            also works on Windows as described under AnsiConsole.  Works with 
            backspace, delete, cursor up/down/left/right, and implements unix 
            shell-style history using alt-left-arrow and alt-right-arrow 
            (alt-up and alt-down on Windows).  Shift-left- and right-arrow 
            (alt-left and alt-right on Windows) move to beginning and end of 
            the current line.  I hope someone likes this because it was 
            painful to implement!

#(mo,rt) returns the terminal mode; in the case of ANSI mode it returns 
a,switches,columns,rows; to see those, you need ##(mo,rt).

6. In ansi mode of #5 above, I have implemented an extended version of
read string: #(rs,init string,displacement): it is as if the user has already 
entered 'init string' with the cursor placed at 'displacement'. If 
'displacement' is positive or 0 is is from the start of the string; if it is 
negative or -0 it is from the end, i.e. '-0' positions the cursor at the very 
end of the string.  This makes scripts like this one, to edit a form, possible:
        
#(ds,edit,(#(ds,**,##(rs,##(cl,**,<1>,<2>,<3>,<4>,<5>,<6>),-0))#(ss,**,<1>,<2>,<3>,<4>,<5>,<6>)))
#(ss,edit,**)

#(edit,form) then allows you to edit 'form'.  Note you must move the cursor to
the end before you hit the meta character, otherwise it will get truncated.
Hitting down-arrow repeatedly is a quick way to move it to the end.

7. I have also added an 'unforgiving' mode: #(mo,e,u) turns it on and 
#(mo,e,-u) turns it off.  It generates error messages and terminates scripts 
for things such as 'form not found', 'too many arguments', 'too few arguments,'
etc.  Per Mooers extra arguments should be ignored, missing arguments filled 
with null strings (with few exceptions such as the block primitives).  There 
may be a few scripts that depend on this feature.  In any case, it is turned 
off as a default.

8. See other extensions to MO in the mode class.

Thanks to Ben Kuhn for getting me Hooked on Pythonics (and for getting me going
on improving RS); to John Levine for consultation, stimulation, and general 
interest; and to Andrew Walker for his enthusiasm and support.

Please feel free to report bugs or request features!

Nat Kuhn (NSK, nk@natkuhn.com)

    TODO: add #(mo,ar) for arithmetic radix and #(mo,br) for boolean radix
    MAYBE: change class names to caps
    KNOWN ISSUE: ANSICON handles wrap to new line differently from xterm,
        with the result that when you type to the last letter the cursor
        advances to the start of the next row.  The result winds up being
        an extra blank line.
"""
# v1.1 implements new RS with cursor keys, input history, etc.
# v1.0 moves the _Getch code into the main module so it all runs out of a single file
# v0.9 fixes a bug in which seg gaps were identical objects, leading to multiple form
# pointers in a single form. Trace implemented per Mooers
# v0.8 cleans up MO, adds STE error, makes RC functional, traps ^C, implements booleans,
#   implements IN.  Complete T-64
# v0.7 cleans up error handling, changes "padto" and "exact" for primitive arguments
#   to "minargs" and "maxargs".  Implements MO
# v0.6 major change is adding endchunk(), eliminating corner cases; partial call
#   primitives now work

# Sample scripts [supplied on GitHub, e.g. use #(fb,fact.trac)]:

#(ds,fact,(#(eq,*,0,1,(#(ml,*,#(fact,#(su,*,1)))))))'
#(ss,fact,*)'

# example: #(fact,5)'120

#(ds,tower,(#(eq,*n,0,,(#(tower,#(su,*n,1),*a,*c,*b)#(ps,(
# Move ring from *a to *c))#(tower,#(su,*n,1),*b,*a,*c)))))'
#(ss,tower,*n,*a,*b,*c)'

# example: #(tower,6,here,middle,there)'

#(ds,exp,(#(eq,*n,0,1,(#(eq,#(rm,*n,2),0,(#(sq,#(exp,*a,#(dv,*n,2)))),(#(ml,*a,
#(exp,*a,#(su,*n,1)))))))))'
#(ss,exp,*a,*n)'
#(ds,sq,(#(ml,*x,*x)))'
#(ss,sq,*x)'

# example: #(exp,2,6)'64

from __future__ import print_function   # for Python 3 compatibility
import re, sys, os, time
import cPickle as pickle                # for SB and FB

class form:
    """a 'form' is a 'defined string.' It is stored as a list; each element in 
    the list is a 'formchunk': either a 'textchunk,'  a 'gapchunk,' or an 
    'endchunk'.  The 'form pointer' falls between characters or between a 
    character and a segment gap.  'pointerchunk' is an int that tells which 
    chunk the form pointer lies in.  A chunk c has a field, c.pointer, that 
    is -1 if the form pointer is outside the chunk, and >= if inside (i.e. 
    the chunk is 'active'.  exitchunk and enterchunk handle this bookkeeping.
    
    In a textchunk, the pointer can only be to the left of a character; if 
    it's at the right end of the chunk, it must actually be at the start of 
    the next chunk.  Hence, if the pointer is at the 'far right' of the form, 
    chunkp points to the terminating endchunk."""
    
    def __init__(self, name, string):
        self.name = name
        forms[name] = self
        if string == '':
            self.formlist = [endchunk()]
        else:
            self.formlist = [textchunk(string), endchunk()]
        self.chunkp = 0     #which chunk has the form pointer
        self.enterchunk()
    
    def val(self,*args):        # for CL
        return ''.join(map(lambda x: x.valchunk(*args),self.formlist[self.chunkp:]))
    
    def segment(self,*args):    # for SS
        self.exitchunk()   
        for segno in range(len(args)):
            segstr = args[segno]
            if segstr == '': continue   # can't segment out null string
            segmented = map( lambda x: x.segmentchunk(segno,segstr), self.formlist )
            self.formlist = sum(segmented , [])
        chunkp = 0          #per Mooers, the form pointer is moved to the left end
        self.enterchunk()

# enterchunk() and exitchunk() are for maintaining the form pointer.
# chunkp is the index in formlist where the formpointer lies.  If ch = formlist[chunkp],
# ch.pointer must be >=0 (and = to 0 for a gapchunk and endchunk).  ch.pointer should be
# -1 for all the other chunks
    def enterchunk(self):
        self.formlist[self.chunkp].pointer=0
    
    def exitchunk(self):
        self.formlist[self.chunkp].pointer = -1
    
    def curchunk(self):
        return self.formlist[self.chunkp]
    
    def atend(self):    # returns True if the form pointer is at the right end of the form
        return self.curchunk().isend()
        
    def resetPointer(self): # for CR
        self.exitchunk()
        self.chunkp = 0
        self.enterchunk()
    
    def toNextChar(self):   # go until a character available or at end
        while not ( self.atend() or self.curchunk().charavail() ):
            self.exitchunk()
            self.chunkp += 1
            self.enterchunk()
        return self.atend()    #true if no character available
    
# toNextChar, getNextChar, toPrevChar, getPrevChar are used in CC and CN
    def getNextChar(self):  # only called after toNextChar returns False
        (ch, toNext) = self.curchunk().getNextCh()
        if toNext:  # at end of text chunk, must advance
            self.exitchunk()
            self.chunkp += 1
            self.enterchunk()
        return ch
    
    def toPrevChar(self):
        # check if inside a text chunk
        if self.curchunk().pointer > 0:
            return False #OK, character ready before form pointer in the current chunk
        while True:
            if self.chunkp == 0: return True  #at the left end, no next character
            if self.formlist[self.chunkp-1].charavail():
                return False    #positioned after a text chunk
            self.exitchunk()
            self.chunkp -=1
            self.enterchunk()
    
    def getPrevChar(self):  # only called after toPrevChar returns False
        p = self.curchunk().pointer
        assert p >= 0
        if p > 0:   #inside a text chunk
            p -= 1
            self.curchunk().pointer = p
            return self.curchunk().text[p]
        else:       #just after a text chunk, at gap or right end
            self.exitchunk()
            self.chunkp -= 1
            self.enterchunk()
            c = self.curchunk()
            c.pointer = len(c.text) - 1
            return c.text[c.pointer]
    
    def validate(self):
        """form.validate() makes sure that a form is valid.  The main loop 
        (psrs(), below) checks each form every time through.  I caught some 
        bugs this way I might not have otherwise."""
        activecount = 0 # chunks with c.pointer>=0, all but 1 chunk should have -1.
        endcount = 0    # endchunks
        previstext = False  # if the previous chunk was text (can't have two in a row)
        invalid = False
        for c in self.formlist:
            if c.pointer >= 0: activecount += 1
            if isinstance(c, textchunk):
                if previstext:
                    ourOS.print_('Invalid form: consecutive text chunks in', self.name, \
                        ':',c.text,'and previous')
                    invalid = True
                previstext = True
                if (c.text) == '':
                    ourOS.print_('Invalid form: null text chunk in',self.name)
                    invalid = True
                if c.pointer >= len(c.text) or c.pointer <-1:
                    ourOS.print_('Invalid pointer (',c.pointer,') in text chunk',c.text)
                    invalid = True
                continue
            previstext = False  #segment gap or end
            if c.pointer < -1 or c.pointer > 0:
                    ourOS.print_('Invalid pointer (',c.pointer,') in gapchunk or endchunk')
                    invalid = True
            if isinstance(c, endchunk): endcount+=1
        if activecount != 1:
            ourOS.print_('Invalid form:',activecount,'active chunks in',self.name)
            invalid = True
        if endcount != 1:
            ourOS.print_('Invalid form: endcount (',endcount,') is illegal in',self.name)
            invalid = True
        if not isinstance(self.formlist[len(self.formlist)-1], endchunk):
            ourOS.print_('Invalid form: endchunk not at end of',self.name)
            invalid = True
        if invalid: ourOS.print_('Invalid form',self.name, ': [', *self.formlist)
        
    def __str__(self):  # used in PF, so the str functions put in the form pointer as <^>
        return ''.join(map(str, self.formlist))
    
    @staticmethod
    def find(name):     # terminates the primitive if the form not found
        if name in forms: return forms[name]
        else: form.FNFError(name)
    
    @staticmethod
    def callCharacter(name,default):    # for CC
        f = form.find(name)
        if f.toNextChar():
            return ( default, True)     #at end, force active
        return (f.getNextChar(), False)
    
    @staticmethod
    def callN(name,numstr,default):     # for CN
        f = form.find(name)
        (n, throwaway, sgn) = mathprim.parsenum(numstr)
        if sgn != '-':      #either '+' or ''
            if f.atend():
                return (default, True)               #return default only if AT end
            if n == 0:
                f.toNextChar()
                return
            chrs = ''
            while n > 0:
                if f.toNextChar(): return (chrs, False)   #null if advancing yields nothing
                chrs += f.getNextChar()
                n -= 1
            return (chrs, False)    # got 'em all, pointer remains to the right of last char
        else:   # sign == '-'...including -0
            if f.chunkp == 0 and f.formlist[0].pointer == 0:
                return (default, True)  #return default only if AT start
            if n == 0:
                f.toPrevChar()
                return
            chrs = ''
            while n < 0:
                if f.toPrevChar(): return (chrs, False) #null if no previous char
                chrs = f.getPrevChar() + chrs   #"prepend" the next character
                n += 1
            return (chrs, False)    # got 'em all, pointer remains to the left of last char
    
    @staticmethod
    def callSeg(name,default):          # for CS
        f = form.find(name)
        if f.atend():     #at right end?
            return ( default, True)     #at end, force active
        (text, skipnext) = f.curchunk().getseg()
        f.exitchunk()
        f.chunkp += 1
        if f.atend():
            f.enterchunk()
            return (text, False)
        if skipnext: f.chunkp += 1  #skip seg gap following text
        f.enterchunk()
        return (text, False)

    @staticmethod
    def deleteall():                    # for DA
        global forms    #for some reason, needed here, but not in 'define', above
        forms = {}
    
    @staticmethod
    def deletedef(*args):               # for DD
        for name in args:
            try:
                del forms[name]
            except:
                if Mode.unforgiving(): form.FNFError(name)
    
    @staticmethod
    def initial(name,text,default):     # for IN
        f = form.find(name)
        findp = f.chunkp
        val = ''
        for chunk in f.formlist[f.chunkp:]:
            (idx, string) = chunk.find(text)
            val += string
            if idx == -1:
                findp += 1
                continue
            break
        else:
            return ( default, True)
        assert idx >= 0
        f.exitchunk()
        newp = idx + len(text)
        if len(f.formlist[findp].text) == newp:
            f.chunkp = findp + 1    #form pointer at end of text chunk, move to start of next
            f.enterchunk()
        else:
            f.chunkp = findp
            f.enterchunk()
            f.formlist[findp].pointer = newp
        return ( val, False )

    @staticmethod
    def FNFError(name):     # used in form.find() and also DD, SB
        raise primError(False, 'form not found (',name,')')

class formchunk:
    """the content of a form is maintained as a list of 'chunks', each chunk is an 
    instance of a subclass of formchunk."""
    def isend(self):
        return False

    def segmentchunk(self,gapno,string):  # only segment textchunks
        return [self]
    
    def charavail(self):
        return False
    
    def find(self,text):
        return ( -1, '' )
    
class textchunk(formchunk):
    """this chunk is for a continuous stream of text between segment gaps"""
    def __init__(self,text):
        self.text = text
        self.pointer = -1
    
    def valchunk(self,*args):
        return self.text if self.pointer == -1 else self.text[self.pointer:]
    
    def getseg(self):
        assert self.pointer >= 0
        return (self.text[self.pointer:], True)  #advance past following segment gap
    
    def segmentchunk(self,gapno,string):
        out = []
        for piece in self.text.split(string):    #will always execute at least once
            if piece != '': out.append(textchunk(piece))
            out.append(gapchunk(gapno))
        out.pop()   # remove final gap
        return out
    
    def getNextCh(self):
        ch = self.text[self.pointer]
        self.pointer += 1
        if self.pointer == len(self.text):
            self.pointer = -1   # perhaps not necessary
            return (ch, True)   # move form pointer to next chunk
        else:
            return (ch, False)
    
    def charavail(self):
        return True     #by definition, pointer is not at end
    
    def find(self,findstr):
        start = self.pointer if self.pointer >= 0 else 0
        find = -1 if findstr == ''  else self.text.find(findstr, start)
        return ( find, self.text[start:] if find < 0 else self.text[start:find] )

    def __str__(self):
        return self.text if self.pointer == -1 \
            else self.text[0:self.pointer] + '<^>' + self.text[self.pointer:]

class gapchunk(formchunk):
    """This chunk represents a segment gap"""
    def __init__(self,gapno):
        self.gapno = gapno
        self.pointer = -1
    
    def valchunk(self,*args):
        return args[self.gapno] if self.gapno<len(args) else ''
    
    def getseg(self):
        return ('', False)  #advance to next chunk, not past it
    
    def __str__(self):
        #oops, trac segment gaps are 1-based, not 0-based!
        return ('<^>' if self.pointer == 0 else '') + '<'+str(self.gapno+1)+'>'
    
class endchunk(formchunk):
    """this chunk needs to go at the end of every form; when the form pointer 
    is at the end (right-hand end) of a form, chunkp points to this chunk.  
    Many corner cases are eliminated by having it."""
    def __init__(self):
        self.pointer = -1
    
    def isend(self):
        return True
        
    def valchunk(self, *args):
        return ''   # value for CL
    
    def getseg(self):   #value for CS--should never happen
        assert False
        
    def __str__(self):
        return '<^>' if self.pointer == 0 else ''

class TheOS:
    """OS-dependent stuff goes here.
    The code for getraw() comes from:
    http://code.activestate.com/recipes/134892/
    and screen-polling code for the future can be found at:
    http://stackoverflow.com/questions/27750135/
    """
    @staticmethod
    def whichOS():
        """note that this method is fixed at compile time; for a runtime-
        based method, or for the origin of this code, see:
        http://stackoverflow.com/questions/4553129/when-to-use-os-name-sys-platform-or-platform-system
        """
        if os.name == 'nt':
            return WindowsOS()
        elif os.name == 'posix':
            if sys.platform == 'cygwin':
                return CygwinOS()
            else:
                return PosixOS()
        else:
            print('Unrecognized OS:',os.name)
            return UnknownOS()
    
    def print_(self,*args,**kwargs):
        print(*args,**kwargs)
        return
    
    def getscrsize(self):
        return None
    
class WindowsOS(TheOS):
    def __init__(self):
        aw = self.getsizeenv()
        self.ansiwidth = aw[1] if aw else None
    
    def getraw(self):
        import msvcrt
        return msvcrt.getch()
    
    def defaultterm(self):
        return 'b'
    
    def rsctrl(self, inp, code):
        if code == 8:
            return AnsiConsole.BS
        if code == 127:         # TODO check this
            return AnsiConsole.DEL
        if code == 224:         # alpha
            ch = tc.inkey()
            if ch == 'H':                  #up arrow
                inp.rowup()
            elif ch == 'P':                #down arrow
                inp.rowdown()
            elif ch == 'K':                #left arrow
                inp.charleft()
            elif ch == 'M':                #right arrow
                inp.charright()
            elif ch == 'S':                #right arrow
                return AnsiConsole.DEL # at least for fn-delete on VMWare
            else:
                tc.bell()     #for the alpha, better late than never
                tc.inbuf = ch + tc.inbuf    # reprocess the character
        elif code == 0:     # NUL
            ch = tc.inkey()
            code = ord(ch)
            if code == 155:         #alt-left arrow
                inp.rowleft()
            elif code == 157:       #alt-right arrow
                inp.rowright()
            elif code == 152:       #alt-up arrow
                tc.dohist('b')
            elif code == 160:       #alt-down arrow
                tc.dohist('f')
            else:
                tc.bell()     #for the alpha, better late than never
                tc.inbuf = ch + tc.inbuf    # reprocess the character
        else:
            tc.bell()

    def getscrsize(self):
        # from http://stackoverflow.com/questions/566746/
        res=None
        try:
            from ctypes import windll, create_string_buffer

            # stdin handle is -10
            # stdout handle is -11
            # stderr handle is -12

            h = windll.kernel32.GetStdHandle(-12)
            csbi = create_string_buffer(22)
            res = windll.kernel32.GetConsoleScreenBufferInfo(h, csbi)
        except:
            return None
        if res:
            import struct
            (bufx, bufy, curx, cury, wattr, left, top, right, bottom, \
                maxx, maxy) = struct.unpack("hhhhHhhhhhh", csbi.raw)
            cols = self.ansiwidth if self.ansiwidth else (right - left + 1)
            rows = bottom - top + 1
            return rows, cols
        else:
            return None
    
    ANSIre = re.compile('(\d+)x(\d+)\s*\((\d+)x(\d+)\)\Z')  #wxh(WxH)
    def getsizeenv(self):
        e = os.getenv('ANSICON')
        if e == None:
            return None
        else:
            m = WindowsOS.ANSIre.match(e)
            try:
                #for ANSICON, return "buffer width" rather than "screen width"
                #because that is where it wraps
                return ( int(m.group(4)), int(m.group(1)) )   # H x w
            except (AttributeError, ValueError):
                raise termError('ANSICON misformatted: ',e)
    
    def newInputString(self,str,point):
        return ACInputString(str,point)     #for ANSICON

class PosixOS(TheOS):
    def getraw(self):
        import sys, tty, termios, fcntl, os
        fd = sys.stdin.fileno()
        old_attr = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_attr)
        return ch
    
    def defaultterm(self):
        return 'a'
    
    def rsctrl(self, inp, code):
        if code == 127:
            return AnsiConsole.BS
        if code == 27:      #ESC
            eseq = tc.geteseq()
            ch = eseq.pop(0)
            if ch == '[':
                if eseq[0] == 'A':                  #up arrow
                    inp.rowup()
                elif eseq[0] == 'B':                #down arrow
                    inp.rowdown()
                elif eseq[0] == 'D':                #left arrow
                    inp.charleft()
                elif eseq == ['1',';','2','D']:     #shift-left arrow
                    inp.rowleft()
                elif eseq == ['1',';','3','D']:     #Cygwin alt-left arrow
                    tc.dohist('b')
                elif eseq[0] == 'C':                #right arrow
                    inp.charright()
                elif eseq == ['1',';','2','C']:     #shift-right arrow
                    inp.rowright()
                elif eseq == ['1',';','3','C']:     #Cygwin alt-right arrow
                    tc.dohist('f')
                elif eseq == ['3','~']:             #delete
                    return AnsiConsole.DEL
                else:
                    tc.bell()     #unrecognized CSI (=esc-[ sequence)
            else:   #eseq doesn't start with [
                if ch == 'b' or ch == 'f':                       #alt-left arrow
                    tc.dohist(ch)
                else:
                    tc.bell()     #for the ESC, better late than never
                    tc.inbuf = ch + tc.inbuf    # reprocess the character
    
    def getscrsize(self):
        # from http://stackoverflow.com/questions/566746/
        def ioctl_GWINSZ(fd):
            try:
                import fcntl, termios, struct, os
                cr = struct.unpack('hh', fcntl.ioctl(fd, termios.TIOCGWINSZ,'1234'))
            except:
                return None
            return cr
        
        cr = ioctl_GWINSZ(0) or ioctl_GWINSZ(1) or ioctl_GWINSZ(2)
        if not cr:
            try:
                fd = os.open(os.ctermid(), os.O_RDONLY)
                cr = ioctl_GWINSZ(fd)
                os.close(fd)
            except:
                pass
        return cr or None

    def getsizeenv(self):
        a = (os.getenv('LINES'), os.getenv('COLUMNS'))
        if a[0] or a[1]:
            return a
        else:
            return None
    
    def newInputString(self,str,point):
        return InputString(str,point)

class CygwinOS(PosixOS):
    def __init__(self):
        # linesep code here
        pass
    
    def print_(self,*args,**kwargs):
        """this is a workaround for a weird cygwin xterm bug that \n becomes
        just lf at times when combined with getraw
        http://stackoverflow.com/questions/28162914/
        """
        args = map(lambda x: '\r\n'.join(x.split('\n')), args)
        if 'end' in kwargs:
            PosixOS.print_(self, *args, **kwargs)
        else:
            PosixOS.print_(self, *args, end='\r\n', **kwargs)
    
class UnknownOS(TheOS):
    #TODO add getraw method to reset to line-mode
    def defaultterm(self):
        return 'l'

class Console(object):
    def __init__(self, *args):
        self.inbuf = ''
        self.settype(*args)
    
    def settype(self,*args):
        prim.condTMA(args, 1, offset=1)
        self.contype = args[0].lower()
    
    def gettype(self):
        return self.contype

    def inkey(self):
        if self.inbuf:
            ch = self.inbuf[0]
            self.inbuf = self.inbuf[1:]
        else:
            ch = ourOS.getraw()
        code = ord(ch)
        if code == 3: 
            raise KeyboardInterrupt     # ^C
        if code == 4:
            raise tracHalt              # ^D
        if code == 13:
            ch = '\n'
        return ch
    
    def readch(self):
        ch = self.inkey()
        self.printstr(ch)
        return ch
    
    def bell(self):
        ourOS.print_( chr(7), end='')
        return
    
    def printstr(self,text):
        ourOS.print_(text, end='')
        return

class BasicConsole(Console):
    """This code was contributed by Ben Kuhn, and subsequently modified.  It
    is for a basic terminal, e.g. the Windows command line, which doesn't
    have the vt100/xterm escape sequences
    """
    def readstr(self, *args):
        """New, improved readstr function. Rather than using stdin.readline(),
        loops on getch(); this allows it to capture the metacharacter 
        immediately, rather than waiting for a newline. If it receives a 
        backspace, it types over the previous character, so everything looks 
        normal. Works fine with copy-paste too.--BSK
        
        1/19/15 NSK: when you backspace past a new line, it goes into 'echoing'
        mode where is types back erased characters between backslashes

        Known issues:
        1. Screws up backspacing when the line is long enough to get soft-
            wrapped by the terminal.
        2. Doesn't work well when you backspace over a printed-out \ from 
            the echoing mode.
        """
        global rshistory
        string = ''
        mc = metachar.get()
        echoing = False #set to true when we BS past \n
        while True:
            ch = self.inkey()
            code = ord(ch)
            if code == 127 or ch == '\b': # backspace (mac or Windows)
                if string == '':
                    self.bell()
                    continue
                # print a space over the character immediately preceding the cursor
                # but we can't backspace over newlines
                if string[-1] == '\n' and not echoing:
                    ourOS.print_('\\',end='')
                    echoing = True
                ourOS.print_(string[-1] if echoing else '\b \b',end='')
                string = string[:-1]
                if string == '' and echoing:
                    ourOS.print_('\\',end='')
                    echoing = False
            else:   #anything else
                if echoing:
                    ourOS.print_('\\',end='')
                    echoing = False
                ourOS.print_(ch, end='')
                if ch == mc:
                    sys.stdout.flush()
                    rshistory.append( string )
                    return string
                else:
                    string += ch

class LineConsole(Console):
    def inkey(self):
        if self.inbuf == '':
            self.inbuf = sys.stdin.readline()
        if self.inbuf == '':    #we've hit EOF
            raise tracHalt
        ch = self.inbuf[0]
        self.inbuf = self.inbuf[1:]
        return ch
    
    def readch(self):
        return self.inkey()
    
    def readstr(self, *args):
        global rshistory
        prim.condTMA(args, 0)
        string = ''
        mc = metachar.get()
        while True:
            ch = self.inkey()
            if ch == mc:
                if mc != '\n' and self.inbuf[0] == '\n':
                    #strip \n immed following meta
                    self.inbuf = self.inbuf[1:]
                rshistory.append( string )
                return string
            else:
                string += ch

ESC = chr(27)

class AnsiConsole(Console):
    """
    RS implementation of unix readline features: cursor keys, and entry 
    history.  Up, down, left,right cursor keys are implemented, along with 
    entry history.
    
    Runs on *nix including OSX, Windows under Cygwin or using Jason Hood's 
    ANSICON.
    
    For ANSICON, see http://adoxa.altervista.org/ansicon/index.html
    Download the full package, use either the x86 (32-bit) or x64 (64-bit).
    Double-click on ANSICON, and then enter "python trac.py -mo,rt,a" 
    (supplying the appropriate paths for the files, if necessary).
    
    Known issue with the Windows Console: when you make the window narrower, 
    it doesn't wrap the lines at the new width, it just makes a scroll bar.  As 
    a result I just leave the line width at buffer width.  If you want a truly
    narrower window, use Cygwin.
    
    Shift-left and shift-right go to beginning and end of line (alt-left
    and alt-right in Windows ANSICON).
    
    Alt-left and Alt-right go backwards and forwards through history (alt-up
    and alt-down in Windows ANSICON).
    
    #(mo,rt,a,switches,columns,rows)
    
    Switches (default is +o+e+l):
    
    The first set of switches has to do with ascertaining the screen size.  It
    tries whichever of the the following methods are enabled (o and e by 
    default), in order, and uses the first successful one.  If +d is enabled
    it tries the other enabled modes and reports any discrepancies--mainly 
    useful for debugging:
    o   get screen size from OS (seems to work pretty universally)
    t   get screen size from polling the terminal using ESC sequences (works
            on OS X Terminal.app and not many others; prints garbage chars
            in ANSICON)
    s   get screen size from using 'tput' in subprocesses (supposedly 
            necessary for cygwin using native Windows Python, but character-
            by-character I/O doesn't work under those circumstances anyway
    e   get screen size from environment variables (does not vary dynamically
            as user resizes screen, so a next-to-last resort)
    f   use fixed screen size, as set by columns, rows; default 80,25. These
            arguments can be present and they set the screen size for +f
            should it be activated in the future
    d   report discrepancies from the above methods
            
    The second set of switches has to do with ascertaining the location of
    the cursor on the screen, mainly used to for figuring out when  up-arrow
    would go off top of screen (default is +l):
    
    l   get screen location by polling the terminal
    v   validate screen position and give error if it isn't correct (errors
            can be thrown by excessively fast typing, or by bug in ANSICON
            on Windows); again mainly for debugging
            
    #(mo,rt) returns a,switches,cols,rows where cols,rows is the actual
        reported size of the screen. Note that for all this to print you need
        to use ##(mo,rt)
    """
    DEFSIZE = (25, 80)
    MINROWS = 4
    MINCOLS = 10
    
    BS = 8
    DEL = 127
    
    def __init__(self, *args):
        self.fixedsize = AnsiConsole.DEFSIZE
        self.carriagepos = 0
        self.sb = SwitchBank('otsefdlv', 'oel')
        Console.__init__(self, *args)
    
    def settype(self, type, *args):
        prim.condTMA(args, 3, offset=2, atmost=True)
        self.contype = type.lower()
        if len(args) >= 1:
            self.sb.flip(args[0])
        if len(args) >= 2:
            try:
                cols = int(args[1])
                rows = int(args[2])
                if rows >= AnsiConsole.MINROWS and cols >= AnsiConsole.MINCOLS:
                    self.fixedsize = (rows, cols)
                else:
                    raise ValueError
            except (ValueError, IndexError):
                raise primError(False, "invalid screen size")
    
    def gettype(self):
        tc.refreshsize()
        return self.contype + ',' + self.sb.vals() + ',' + \
            str(self.scrsize[1]) + ',' + str(self.scrsize[0])
    
    def adjustcarriage(self,t):
        p = t.split('\n')
        if len(p) == 1: self.carriagepos += len(p[0])
        else:  self.carriagepos = len(p[-1])
        return
    
    def printstr(self,text):
        Console.printstr(self,text)
        self.adjustcarriage(text)
        return
    
    def refreshsize(self):
        self.results = []
        self.trysize('o', 'OS', ourOS.getscrsize)
        self.trysize('t', 'terminal poll', self.sizepoll)
        self.trysize('s', 'subprocess', self.sizeproc)
        self.trysize('e', 'environment', ourOS.getsizeenv)
        if not self.results:    #none so far, go to fixed option
            self.sb.switches['f'] = True
        self.trysize('f', 'fixed', lambda: self.fixedsize )
        (self.scrsize, scrsource) = self.results[0]
        if self.sb.switches['d']:
            discrep = False
            for ( size, source ) in self.results[1:]:
                if size == self.scrsize:
                    continue
                ourOS.print_("Screen size discrepancy:",self.scrsize,'from',\
                    scrsource,"vs",size,'from',source)
                discrep = True
            if discrep:
                self.sb.switches['d'] = False    # once is enough
    
    def trysize(self,flag,name,fn):
        if self.sb.switches[flag] == False: # this method is disabled
            return
        if self.sb.switches['d'] == False and self.results:  # or we already 
            return  # have a result and aren't interested in discrepancies
        size = fn()
        if size == None:
            self.sb.switches[flag] = False  # don't retry if it fails
        else:
            self.results.append( (size, name) )
                
    def sizepoll(self):
        ourOS.print_(ESC + '[1 8t', end='')
        return self.getcoords('t','8',';')
    
    def sizeproc(self):
        try:
           import subprocess
           proc=subprocess.Popen(["tput", "cols"],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
           output=proc.communicate(input=None)
           cols=int(output[0])
           proc=subprocess.Popen(["tput", "lines"],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
           output=proc.communicate(input=None)
           rows=int(output[0])
           return (rows,cols)
        except:
           return None
    
    def getcoords(self, term, *args):
        """this is a utility function to input the results of device-polling
        escape sequences.
        If it takes > 50 msec to get to ESC, we conclude that device-polling
        is not working."""
        time0 = time.time()
        while True:
            ch = ourOS.getraw()
            if (time.time() - time0) <= 0.05:
                if ch == ESC: break
                self.inbuf += ch
            else:
                self.inbuf += ch
                return None
        seq = self.geteseq()
        start = ['['] + list(args)
        while len(start) > 0:
            if (len(seq) == 0) or (seq[0] != start[0]):
                raise termError("Expecting '",start[0],"' at start of device poll, didn't find it.")
            start.pop(0)
            seq.pop(0)
        if seq.pop(-1) != term:
            raise termError("Expecting '",term,"' at end of device poll, didn't find it.")
        try:
            i = seq.index(';')
            xstr = ''.join(seq[:i])
            ystr = ''.join(seq[i+1:])
            return ( int(xstr), int(ystr) )
        except ValueError:
            raise termError("Value '",''.join(seq),"' from device poll is not well-formed.")

    def geteseq(self):
        """
        this routine is called after an ESC is received.  It gathers the 
        escape sequence characters and returns them as a list.
        
        it does a good job handling CSI-escape sequences, i.e. esc-[
        it does not necessarily handle non-CSI sequences well
        if it doesn't start with [, then the next character is just returned
        https://en.wikipedia.org/wiki/ANSI_escape_code
        http://invisible-island.net/xterm/ctlseqs/ctlseqs.html
        """
                    
        seqlist = []
        while True:
            ch = ourOS.getraw()
            code = ord(ch)
            seqlist.append(ch)
            if len(seqlist) == 1:
                if ch != '[': return seqlist
            else:   #len > 1
                if ( (code >= 64) and (code < 127) ): return seqlist
    
    def readstr(self, *args):
        """
        Known issues:
        1. In OS X Terminal, if you type cmd-K to kill scrollback at "> " 
            prompt, and then type "ab'", it erases "> ab" leaving blank then 
            "'ab".  This seems to be a bug in the Mac Terminal program, which I 
            can reproduce in my "screenplay.py" test program.
        2. ^C or ^D with cursor in hanging position overwrites last character
        3. screen resize can cause cursor to wrap to next line rather than 
            going into hanging location
        4. with meta = \n, go one character over the end of the line, cursor 
            back, and hit enter; it prints a blank line, unlike hitting enter 
            at the very end of the line
        5. typing close parens to rapidly causes failure with paren matching,
            at least on input with a \n in the middle.
        """
        mc = metachar.get()
        self.histpointer = None
        #handle arguments to RS
        if len(args) > 0 and Mode.extprim():
            prim.condTMA(args, 2, atmost=True)
            startstr = args[0]
            if len(args) < 2:
                startpoint = '0'
            else:
                startpoint = args[1]
            (startnum, dummy, sign) = mathprim.parsenum(startpoint)
            if sign == '-':
                startnum += len(startstr)
            if startnum < 0: startnum = 0
            startnum = min(startnum, len(startstr) )
            self.inp = InputString.new(startstr, startnum)
            ourOS.print_(startstr, end='')
            self.refreshsize()
            self.inp.cursorisat( len(startstr) )
            self.inp.curtoinspoint()
        else:
            prim.condTMA(args,0)
            self.inp = InputString.new('',0)
        
        while True:             #RS main loop
            try:
                ch = self.inkey()
            except (KeyboardInterrupt, tracHalt):
                self.inp.eprint('')
                raise
            code = ord(ch)
            if (code < 32 or code >=127) and ch != '\n':
                code = ourOS.rsctrl(self.inp, code)
                if code == None:    #nothing more to process
                    continue
            if code == AnsiConsole.BS: # backspace
                if self.inp.inspoint == 0:
                    self.bell()
                    continue
                self.inp.curatinspoint()
                tail = self.inp.rstring[self.inp.inspoint:]
                self.inp.inspoint -= 1
                head = self.inp.rstring[0:self.inp.inspoint]
                self.inp.rstring = head+tail
                self.inp.redolengths()
                self.inp.curtoinspoint()
                self.inp.eprint(tail)
                if self.inp.inspoint == len(self.inp.rstring):
                    continue        #already in the right place
                self.inp.cursorisat(len(self.inp.rstring) )
                self.inp.curtoinspoint()
            elif code == AnsiConsole.DEL:
                if self.inp.inspoint == len(self.inp.rstring):
                    self.bell() #already at end, nothing to del
                    continue
                self.inp.curatinspoint()
                head = self.inp.rstring[0:self.inp.inspoint]
                tail = self.inp.rstring[self.inp.inspoint+1:]
                self.inp.rstring = head+tail
                self.inp.redolengths()
                self.inp.eprint(tail)
                if self.inp.inspoint == len(self.inp.rstring):
                    continue        #just deleted last char
                self.inp.cursorisat( len(self.inp.rstring) )
                self.inp.curtoinspoint()
            else:   #printable or \n
                self.inp.curatinspoint()
                head = self.inp.rstring[0:self.inp.inspoint]
                if ch == mc:    #meta: delete the rest and return the head
                    self.inp.eprint(ch)
                    self.adjustcarriage(head + mc)   #remember, mc could be \n
                    self.inp.rstring = head
                    self.inp.redolengths()
                    rshistory.append( head )
                    sys.stdout.flush()
                    return head
                tail = self.inp.rstring[self.inp.inspoint:]
                self.inp.rstring = head + ch + tail
                self.inp.redolengths()
                # there is a knotty problem with hitting the enter key with
                # cursor at first character of a wrapped line; it should not
                # change screen but should insert \n
                if self.inp.colloc == 1 and self.inp.pos > 0 and ch == '\n':
                    self.inp.eprint(tail)
                else:
                    self.inp.eprint(ch + tail) #even if it's printable, need to erase due to linewrapping
                self.inp.inspoint += 1
                if self.inp.inspoint != len(self.inp.rstring):
                    self.inp.cursorisat( len(self.inp.rstring) )
                    self.inp.curtoinspoint()
                if ch == ')':
                    self.inp.parenmatch()        # end of RS main loop
    
    def dohist(self, dir):
        if self.histpointer == None:    #set up history
            self.histcopy = map(lambda x: InputString.new(x,len(x)), rshistory)
            self.histpointer = len(self.histcopy)
            self.histcopy.append(self.inp)
        if dir == 'b':       #move back
            if self.histpointer == 0:
                self.bell()     #moving before start
                return
            else:
                self.histpointer -= 1
        elif dir == 'f':     #move forward
            if self.histpointer >= len(self.histcopy) - 1:
                self.bell()     #moving after end
                return
            else:
                self.histpointer += 1
        else:
            assert False
        self.inp.curatinspoint()
        self.inp.cursorto(0)
        
        #now need to show the new self.inp
        newinp = self.histcopy[self.histpointer]
        self.refreshsize()
        newinp.cursorisat(0)
        newinp.eprint(newinp.rstring)
        self.inp = newinp
        if newinp.inspoint == len(newinp.rstring):
            return        #already in the right place
        newinp.cursorisat( len(newinp.rstring) )
        newinp.curtoinspoint()
        return

Console.condict = dict( a=None, b=None, l=None)
Console.contypes = dict( a=AnsiConsole, b=BasicConsole, l=LineConsole )

class InputString(object):
    """
    This class is a container for the RS input string when doing xterm/VT100-
    style input.  It also contains most of the methods to make that function.
    
    The problem is actually quite complex: not only can the screen scroll, but 
    the user can resize the screen at any time, resulting in lots of movement 
    due to soft-wrapping of lines.
    
    The implementation is further complicated by the "hangover" effect: when 
    characters are printed to the very end of a line, the cursor does not 
    advance to the next line.  This makes sense, because if the next "printed" 
    character is \n, you would like to simply go to the next line rather than 
    leave a blank line.
    
    When the cursor is in the last column, it can simply be in the last column 
    (in which case a printed character will go in the last column, and inserted
    characters should be inserted _before_ the character in the last column; 
    or it can be in "hanging position" in which case a printed character will 
    wrap to the next line, and inserted characters should be inserted _after_ 
    the character in the last column.
    
    Resizing the screen interacts with this in unpredictable ways.  On Mac OSX 
    Terminal app, if you are in hanging position and resize the screen to make 
    the line longer, the next type character will _still_ wrap to the next 
    line.  This means that even if the cursor was positioned "where you want 
    it," you can't count on it staying there.  Another example of bad behavior:
    if you type a line normally, so that the cursor is after the last 
    character, and then resize the line so the last character is in the last 
    column, the cursor is put into the last column, _but not in hanging
    position_, so that the next typed character over-writes the last character,
    rather than wrapping to the next line.  This means that to get the correct 
    results with screen-resizing, you need to print escape codes with every 
    character typed.
    
    "point" refers to 0-based position (index) within the entire input string
    "pos" refers to position within a "virtual line".  A VL may wrap and appear
        on several screen lines.  As the screen is resized the actual screen 
        location will change.
    "loc" refers to the actual location on the screen.
    linelengths[] is a list containing the lengths of the lines in the input 
        string. linelengths[0] includes the length of the "prompt" which is 
        in tc.carriagepos
    
    rstring is the actual input string
    inspoint is the index in rstring where the current insertion point is
    curpoint is the index in rstring corresponding to the location where the 
        screen cursor is supposed to be located. this will be different from 
        inspoint, e.g. if we have just rewritten the end of the string on the 
        screen
    rowloc,colloc: the screen coordinates of the current cursor; the column
        is set programmatically, while the row could be set by device polling, 
        or not.
    tc.scrsize: the size of the screen (r,c), determined by refreshsize()
    rowsdown: the number of screen rows from the start of "line 0" (i.e. the 
        beginning of the "virtual line" that input string stars on) to the
        current screen cursor location
    hanging: True if the actual cursor location is intended to be in hanging 
        position. The terminal emulator may or may not be, and the code should
        be written independent of that if possible, because terminal programs
        may not be consistent.
    line: the virtual line that curpoint is in
    pos: the index within the virtual line
    
    tc.carriagepos is the position within the current "line". It is set by PS, 
        and at the END of RS
    """
    FLASHSECS = .150    # amount of time to flash for paren matching
    
    @staticmethod
    def new(str,point):
        return ourOS.newInputString(str,point)
    
    def __init__(self, str, point):
        self.rstring = str
        self.inspoint = point
        self.redolengths()
        tc.refreshsize()
        self.posfrompoint(point)    #initialize self.hanging, so hitting
            # ^C or ^D as first input char doesn't generate exception
    
    def redolengths(self):
        self.linelengths = map(len,self.rstring.split('\n'))
        self.linelengths[0] += tc.carriagepos
    
    def posfrompoint(self, point):
        """
        this sets curpoint to 'point', and computes the (virtual) line and pos 
        corresponding to that point. It also tells how many screen rows it
        should be down from the start of line 0 on a screen with scrsize[1] 
        columns. it sets 'hanging' if printing to here would leave cursor in 
        hanging position; the actual printed character may or may not actually 
        be in hanging position.
        
        used in cursorisat() and cursorto()
        """
        self.curpoint = point
        self.pos = tc.carriagepos + point
        rd = 0
        for self.line in range(len(self.linelengths)):
            ll = self.linelengths[self.line]
            self.colloc = self.pos % tc.scrsize[1] + 1
            if self.pos == 0 or self.pos < ll:    #not hanging, for sure
                self.rowsdown = rd + self.pos // tc.scrsize[1]
                self.hanging = False
                return
            if self.pos == ll:  #hanging, if scrsize[1] goes into chars evenly
                self.rowsdown = rd + (self.pos-1) // tc.scrsize[1]
                if self.colloc == 1:
                    self.hanging = True
                    self.colloc = tc.scrsize[1]
                else:
                    self.hanging = False
                return
            self.pos -= (ll + 1)       # count 1 for the \n
            rd += max(0, ll-1) // tc.scrsize[1] + 1           # same here
                # use ll-1 because an 80-char line on an 80-char screen won't 
                # wrap, i.e. the returned value says "if I just printed that, 
                # how many lines down will I be," rather than "if I want to 
                # move the insertion point here, how many lines down should 
                # it be?" #hangovereffect
        raise termError("Logic error (posline): curpoint=",self.curpoint, \
            'linelengths=',self.linelengths, ", overflow=",self.pos)

    def cursorisat(self, point):
        """
        "point" is the position in the RS input string where the cursor is 
        supposed to be currently
        
        this needs to be called with some frequency because the screen can be 
        resized between any two keystrokes
        
        it defaults to getting the screen size, but 'reusesize=True' will, uh,
        reuse the previous size
        
        it sets the parameters using posfrompoint()
        
        it gets the current location and then (partially) validates that the 
            current screen cursor position corresponds to 'point'
        """
        self.posfrompoint(point)    # depends on tc.scrsize[1]
        self.refreshloc()           # gets row location, if available
    
    def curatinspoint(self):
        tc.refreshsize()
        self.cursorisat(self.inspoint)
    
    def cursorto(self, newpoint):
        """
        cursorto moves the screen cursor from curpoint to 'newpoint'.
        
        cursorto is used by cursor key handling, repositioning the cursor after 
        printing to the screen, repositioning before backspace/delete, and
        paren matching
        """
        fromrow = self.rowloc
        rowsup = self.rowsdown
        self.posfrompoint(newpoint)
        rowdelta = self.rowsdown - rowsup
        if self.rowloc != None:
            self.rowloc += rowdelta
            if self.rowloc <= 0:
                #TODO this should not be termError? those should only be for things that
                raise termError("<ERR> New cursor position is off the top of the screen")
        self.scrgoto(rowdelta,self.colloc)
        if tc.sb.switches['v']:
            shouldbe = self.rowloc
            self.refreshloc()
            if self.rowloc != shouldbe:
                raise termError('Row alignment error: rowloc=', shouldbe, \
                    ' but actually is ', self.rowloc)
        return
    
    def curtoinspoint(self):
        self.cursorto(self.inspoint)
    
    def scrgoto(self, delta, col):
        # note that using E/F instead of B/A might enable rollback on the 
        # screen, eliminating the error message in cursorto()
        if delta < 0:
            ourOS.print_(ESC + '[' + str(-delta) + 'A', end='')
        elif delta > 0:
            ourOS.print_(ESC + '[' + str(delta) + 'B', end='')
        ourOS.print_(ESC + '[' + str(col) + 'G', end='')
    
    def eprint(self, s):
        """erase to end of screen. eprint is used (a) when inserting the meta 
        char, the rest of the input string is discarded; (b) when inserting a 
        newline; and (c) when backspacing; (d) with ^C or ^D
        """
        start = 0
        if self.hanging:
            if self.rowloc == tc.scrsize[0]:   #last character on screen
                if s == '': return
                self.rowloc -= 1  #the screen will roll up 1
            ourOS.print_('\n',end='')
            if s == '':
                ourOS.print_(ESC+'[J', end='')
                self.scrgoto(-1, tc.scrsize[1])  # go back up
                return
            if s[0] == '\n': start = 1
        ourOS.print_(ESC+'[J'+s[start:], end='')
    
    def refreshloc(self):
        if tc.sb.switches['l'] == False:
            self.rowloc = None
            return
        ourOS.print_(ESC + '[6n', end='')
        coords =  tc.getcoords('R')
        if coords == None:  #couldn't get from poll
            self.rowloc = None
            tc.sb.switches['l'] = False  # don't keep trying
            return
        self.rowloc = coords[0]
        if self.colloc == coords[1]:
            return
        if tc.sb.switches['v']:
            raise termError('Column alignment error: colloc=', \
                self.colloc, ' but actually is ', coords[1])
    
    def charleft(self):
        if self.inspoint == 0:
            tc.bell()
        else:
            self.curatinspoint()
            self.inspoint -= 1
            self.curtoinspoint()
    
    def charright(self):
        if self.inspoint == len(self.rstring):
            tc.bell()
        else:
            self.curatinspoint()
            self.inspoint += 1
            self.curtoinspoint()
    
    # remember that in line 0, "pos" includes the prompt (tc.carriagepos) which
    # can span several rows. the code above guarantees that if we're in line 0,
    # self.inspoint > scrsize[1]
    def rowup(self):
        if self.inspoint == 0:
            tc.bell()
            return
        self.curatinspoint()
        if self.line == 0 or self.pos >= tc.scrsize[1]:   #go as straight up as poss
            self.inspoint = max(0, \
                self.inspoint - tc.scrsize[1] - (1 if self.hanging else 0) )
            self.curtoinspoint()
            return
        prevll = self.linelengths[self.line-1]
        onprevrow = 0 if prevll == 0 else \
            (prevll - 1) % tc.scrsize[1] + 1  #number of chars on the prev row
        # OK, we want to move straight up, how much do we move self.inspoint?
        # if the last row were the full width of the screen, self.inspoint
        # would go back scrsize[1]+1 (the extra 1 for the \n). But that is going
        # too far back by scrsize[1]-onprevrow. this works out to the formula
        # above. geometrically, if you take the characters on the last row and
        # move the first "pos" of them down to the current row, you will see
        # that this give you the # of chars to back up (with an additional 1
        # for the newline)
        if self.pos > onprevrow:    # we're past the end of prev row, so go to end of row
            self.inspoint -= self.pos+1 #+1 for the \n
        else:
            self.inspoint -= onprevrow + 1
        self.inspoint = max(0,self.inspoint)  #could be -ve if we went up into the prompt
        self.curtoinspoint()
        return
    
    def rowdown(self):
        if self.inspoint == len(self.rstring):   #already at the very end
            tc.bell()
            return
        self.curatinspoint()
        curll = self.linelengths[self.line]
        rump = curll - self.pos  #how much left on this line?
        if rump >= tc.scrsize[1]:  
            self.inspoint += tc.scrsize[1]
            #check if this leaves in hanging position
            if rump == tc.scrsize[1] and self.colloc == 1: self.inspoint += 1
        #already on last line, just go to the end
        elif self.line == len(self.linelengths) - 1:
            self.inspoint = len(self.rstring)
        #some of this line, hangs over, but not enough to go straight down,
        #go to the end of it
        elif rump + self.colloc > tc.scrsize[1] + 1:
            self.inspoint += rump
        else:   # go to next line
            nextll = self.linelengths[self.line + 1]
            self.inspoint += rump + min(self.colloc, nextll + 1)
            # if the line is too short, just go to the end of it
            # note the self.colloc already includes the "+1" for the \n
        self.curtoinspoint()
        return
    
    def rowleft(self):    #move cursor back to start of row
        self.curatinspoint()
        if self.colloc == 1 or self.inspoint == 0:     #already there?
            tc.bell()
            return
        self.inspoint -= self.colloc - (1 if not self.hanging else 0)
        self.inspoint = max(self.inspoint, 0)     #don't go back into prompt
        self.curtoinspoint()
        return
    
    def rowright(self):   #move cursor forward to end of row
        if self.inspoint == len(self.rstring) or self.rstring[self.inspoint] == '\n':
            tc.bell()      #already there
            return                
        self.curatinspoint()
        charsleft = self.linelengths[self.line] - self.pos
        if charsleft == 0:      #already there
            tc.bell()
            return
        colsleft = tc.scrsize[1] - self.colloc
        gohang = ( charsleft - colsleft ) == 1
        if colsleft == 0 and not gohang:    #already there
            tc.bell()
            return
        self.inspoint += min(charsleft, colsleft) + (1 if gohang else 0)
        self.curtoinspoint()
        return
    
    def parenmatch(self):
    #TODO bad things will happen if paren match rolls off top of screen
        i = self.inspoint - 1
        bal = 0
        while i >= 0:
            c = self.rstring[i]
            if c == ')':
                bal += 1
            elif c == '(':
                bal -= 1
                if bal == 0:
                    self.cursorto(i)
                    sys.stdout.flush()
                    time.sleep(InputString.FLASHSECS)
                    self.curtoinspoint()
                    return
            i -= 1
        if bal > 0: # too many )
            tc.bell()

class ACInputString(InputString):
    """This class is to deal with the fact that ANSICON handles the final
    column differently from xterm: after printing in the last column it wraps
    to the next line.  If the next character printed is \n, it is ignored.
    
    self.hanging is only used in eprint, rowup, and rowleft.  If we set it
    false at all times, should work
    """
    def posfrompoint(self, point):
        self.curpoint = point
        self.pos = tc.carriagepos + point
        rd = 0      # rows down
        self.hanging = False
        for self.line in range(len(self.linelengths)):
            ll = self.linelengths[self.line]
            self.colloc = self.pos % tc.scrsize[1] + 1
            if self.pos <= ll:    #not hanging, for sure
                self.rowsdown = rd + self.pos // tc.scrsize[1]
                return
            self.pos -= (ll + 1)       # count 1 for the \n
            rd += max(0, ll-1) // tc.scrsize[1] + 1           # same here
                # use ll-1 because an 80-char line on an 80-char screen won't 
                # wrap, i.e. the returned value says "if I just printed that, 
                # how many lines down will I be," rather than "if I want to 
                # move the insertion point here, how many lines down should 
                # it be?" #hangovereffect
        raise termError("Logic error (posline): curpoint=",self.curpoint, \
            'linelengths=',self.linelengths, ", overflow=",self.pos)

    def eprint(self, s):
        """erase to end of screen. eprint is used (a) when inserting the meta 
        char, the rest of the input string is discarded; (b) when inserting a 
        newline; and (c) when backspacing; (d) with ^C or ^D
        """
        ourOS.print_(ESC+'[J'+s, end='')

class specchar:
    """a container for the 'meta character' which terminates #(RS), and the 
    'syntax character' (default, #), which is not changeable in the T-64 spec, 
    but which Claude Kagan used as :.  It can be changed with #(mo,ms,x) which 
    is how John Levine remembers it, and I think he's right"""
    def __init__(self,ch):
        self.ch = ch
    
    def get(self):
        return self.ch
    
    def set(self,new,exclude):
        if new == '':
            raise primError(False, 'cannot change to null string')
        newch = new[0]
        if newch in '()'+exclude:     #bad to change
            raise primError( False, "cannot change to '", newch, "'" )
            return #False this said return False, but that can't be right NSK 1/7/15
        if (ord(newch) < 32 and newch != '\n') or ord(newch) > 126:
            raise primError( False, "cannot change to non-printing character" )
            return
        else:
            self.ch = newch

class syntclass(specchar):  # subclass for the syntax char, since it needs to update the re
    def __init__(self,ch):
        specchar.__init__(self,ch)
        self.setre()
    
    def set(self,new,exclude):
        specchar.set(self,new,exclude)
        self.setre()
    
    def setre(self):
        self.syntre = re.compile('['+self.ch+'(),\n]')
    
    def getre(self):
        return self.syntre
    
class block:      # static class to handle the block (disk storage) primitives.
    @staticmethod
    def store(*args):           # for SB
        if len(args) == 0: prim.TFAError(0,1,True)   # expecting 1 or more
        sblist = []
        for n in args[1:]:
            if n in forms:
                f = forms[n]    #can't use form.find b/c it terminates if not found
                if f not in sblist: sblist.append(f)
            else:
                if Mode.unforgiving(): form.FNFError(n)
        try:
            with file(args[0], 'w') as out:
                pickle.dump(sblist, out)    # potential problem if forms modified by ss?
        except IOError as e:
            raise tracError(True, '<STE> ',e)
        for f in sblist: del forms[f.name]  #delete the forms as per Mooers p.66
    
    #FB and EB can't use standard "exact=1" because #(FB) should NOT default to #(FB,)
    #per Mooers
    @staticmethod
    def fetch(*args):           # for FB
        l = len(args)
        if l == 0: prim.TFAError(0,1,False)     # expecting 1
        prim.condTMA(args,1)
        try:
            with file(args[0]) as input:
                fblist = pickle.load(input)
        except IOError as e:
            raise tracError(True, '<STE> ',e)
        for f in fblist: forms[f.name] = f
    
    @staticmethod
    def erase(*args):           # for EB
        l = len(args)
        if l == 0: prim.TFAError(0,1,False)     # expecting 1
        prim.condTMA(args,1)
        try:
            os.remove(args[0])
        except OSError as e:
            raise tracError(True, '<STE> ',e)
    
class tracHalt(Exception):  # used for HL and for EOF (^D) on stdin
    def __init__(self):
        raise self

class tracError(Exception):
    """the first of the args is True if the error message is to be given even
    when Mode.unforgiving() is False.  The other args are joined together to 
    form the message.  As of now the only use for the True setting is the 
    <STE> errors"""
    
    def __str__(self):
        return ''.join(map(str,self.args[1:]))
    
class primError(Exception):
    """this is for 'primitive errors.'  The first of the args is False if the 
    primitive should simply abort and return a null value unless 
    Mode.unforgiving() is True, in which case execution will stop and the 
    message will be displayed.  If the first arg is True, execution is halted 
    and the message is displayed no matter what."""
    pass

class termError(Exception):
    """this is for unexpected problems with escape sequences"""
    def __str__(self):
        return ' '.join(map(str,self.args))

class SwitchBank:
    def __init__(self,all,ons):
        self.switches = {}
        for x in list(all):
            self.switches[x] = x in ons
    
    sre = re.compile('([-+]?)([a-zA-Z])')
    
    def flip(self,swstring):
        i = 0
        while i < len(swstring):
            m = SwitchBank.sre.match(swstring[i:])
            try:
                self.switches[m.group(2).lower()] = \
                    (m.group(1) != '-') #'+' or '' are ON
                i += m.end()
            except (AttributeError, KeyError):
                raise primError(False, 'unrecognizable switch string: ', \
                    swstring[i:])
    
    def vals(self):
        s = ''
        for k,v in self.switches.items():
            s += ('+' if v else '-') + k
        return s
            
class Mode:     # for MO
    """
    #(mo) goes into T-64 regulation mode, blocking extended features like 
    extended primitives like #(rm,5,2) or #(rs,string,offset).
    
    #(mo,e) allows extended features; it's the default
    
    #(mo,s) controls the features which are activated when #(mo,e) is 
    executed.  #(mo,s,switches) allows the following switches:
        +/- p for extended primitives, and
        +/- u for unforgiving errors (such as "too many arguments")
    e.g. #(mo,s,-p+u) sets no extended primitives but unforgiving errors
    #(mo,s) by itself return the state of those switches
    #(mo,ms,:) modifies the syntactic character, in this case to ':', following
    C.A.R. Kagan... apparently this was easier to type on a Teletype; it's no 
    easier on a standard keyboard, so I switched to the # camp... especially 
    since you can put scripts in as Python comments, and not have to edit out 
    initial #s.
    """
#must be defined above primitives, in case there is a duplicate
    swextended = SwitchBank('pu','p')   # default is extended prims
    swunext = SwitchBank('pu','')
    swactive = swextended               # default is #(mo,e) on startup
    
    @staticmethod
    def unforgiving():
        return Mode.swactive.switches['u']
    
    @staticmethod
    def extprim():
        return Mode.swactive.switches['p']
    
    @staticmethod
    def extended(m=None):
        if m == None:
            return Mode.swactive == Mode.swextended
        else:
            Mode.swactive = Mode.swextended if m else Mode.swunext
    
    @staticmethod
    def setmode(*args):
        if len(args) == 0:  # #(MO): meet the T-64 spec
            Mode.extended(False)
            return
        modearg = args[0].lower()
        if modearg == 'e':
            prim.condTMA(args,1)
            Mode.extended(True)
        elif modearg == 'ms':    # C. A. R. Kagan extension to Modify Syntax character
            prim.condTMA(args,2)
            syntchar.set( '' if len(args) == 1 else args[1], metachar.get() )
        elif modearg == 's':    #switches when extended mode activated
            prim.condTMA(args,2)
            if len(args) == 1:
                return Mode.swextended.vals()
            else:
                Mode.swextended.flip(args[1])
        elif modearg == 'rt': #reactive typewriter
            return Mode.setcontype(*args[1:])
        else:
            raise primError(False, 'unrecognized mode: ', modearg)
    
    @staticmethod
    def setcontype(*args):
        global tc
        if len(args) == 0:
            return tc.gettype()
        c = args[0].lower()
        oldtc = tc
        try:
            tc = Console.condict[c]
            if tc == None:      #need to instantiate
                tc = Console.condict[c] = Console.contypes[c](*args)
            else:
                tc.settype(*args)
        except KeyError:
            tc = oldtc
            raise primError(False, 'unrecognized console type: ', c)
        except primError:       # e.g. too many args
            tc = oldtc
            raise
    
def trace(*args):       # a flag, used in TN and TF
    global tracing
    if len(args) == 0:
        return tracing
    else:
        tracing = args[0]
        return

class prim:
    """each 'primitive' is an instance of this class, or its active subclass 
    mathprim"""
    def __init__(self,name,f,**kwargs):
        self.name = name
        self.fn = f
        self.extended = kwargs['extended'] if 'extended' in kwargs else False
        if 'exact' in kwargs:
            self.minargs = kwargs['exact']
            self.maxargs = kwargs['exact']
        else:
            self.minargs = kwargs['minargs'] if 'minargs' in kwargs else 0
            self.maxargs = kwargs['maxargs'] if 'maxargs' in kwargs else -1
        if name in prims:
            raise tracError(True, 'system error: duplicated primitive: ', name)
        prims[name] = self  # add self to list of primitives
    
    def __call__(self,*args):
        try:
            args = self.fixargs(*args)
            val = self.fn(*args)
        except primError as p:
            if Mode.unforgiving() or p.args[0]:   #interrupt execution
                raise tracError(True, '<UNF> (', self.name, ') ',*p.args[1:])
            else:
                return ''
        if val == None: return ''
        else: return val
    
    def fixargs(self,*args):    #pads if necessary, and checks too many or too few
        l = len(args)
        if Mode.unforgiving():
            if l < self.minargs:
                prim.TFAError(l, self.minargs, self.minargs != self.maxargs )
            if self.maxargs >= 0 and l > self.maxargs: 
                prim.TMAError(l, self.maxargs)
        padlen = max(self.minargs, self.maxargs)    # e.g. EQ has min=3, max=4
        # because you might conceivably want a null last argument... but need 4 args
        if padlen > l:
            args += ('',) * (padlen-len(args))
        if self.maxargs >= 0 and self.maxargs < len(args):  #could probably put 'l' there
            args = args[0:self.maxargs]
        return args
    
    @staticmethod
    def TMAError(has,expecting, atmost=False):
        raise primError(False, 'too many arguments: has ',has,', expecting ', \
            'at most ' if atmost else '', expecting)
    
    @staticmethod
    def TFAError(has,expecting,ormore):
        raise primError(False, 'too few arguments: has ',has,', expecting ', expecting, \
            ' or more' if ormore else '')
    
    @staticmethod
    def condTMA(args, num, offset=0, atmost=False ):
        if len(args) > num and Mode.unforgiving():
            prim.TMAError(len(args) + offset, num + offset, atmost=atmost)
    
class mathprim(prim):   # for AD, SU, ML, DV, RM
    numre = re.compile(r'^(.*?)([+-]?)([0-9]*)\Z',re.DOTALL) #initial ^ is redundant for match
    
    def __call__(self,*args):
        args = self.fixargs(*args)     #tuples are immutable
        try:
            (x, prefix) = mathprim.parsenum( args[0] )[0:2]
            y = mathprim.tracint( args[1] )
            val = self.fn( x, y )
        except ZeroDivisionError:
            return (args[2], True)  # return 'default string' which must be executed as active
        return prefix + str(val)
        
    @staticmethod
    def parsenum(arg):
        """returns (signed numerical part, prefix part, sign) as per p.53 of 
        Mooers [1972] note that CN distinguishes -0 from 0....
        This is used in the extended form of #(rs)"""
        m = mathprim.numre.match(arg)
        unsignedstr = m.group(3)
        u = 0 if unsignedstr=='' else int(unsignedstr)
        sign = m.group(2)
        return ( -u if sign=='-' else u, m.group(1), sign )
    
    @staticmethod
    def tracint(x):     # used above, and also in GR
        return mathprim.parsenum(x)[0]

class boolprim(prim):
    """this is really a class for static methods, not one we create instances of"""
    
    boolre = re.compile(r'([0-7]*)\Z')
    
    @staticmethod
    def parsebool(arg):
        m = boolprim.boolre.search(arg)
        assert m != None
        octalstr = m.group(1)
        l = len(octalstr)
        bits = 0 if l==0 else int(octalstr,8)
        return (bits, l)    # the value, the length
    
    @staticmethod
    def tooct(bits, width):
        if width == 0: return ''
        else: return ('{:0'+str(width)+'o}').format(bits)
    
    @staticmethod
    def mask(len):
        return ( 1 << len*3 ) - 1
    
    @staticmethod
    def union(b1,b2):
        (val1, len1) = boolprim.parsebool(b1)
        (val2, len2) = boolprim.parsebool(b2)
        return boolprim.tooct( val1 | val2, max(len1, len2) )
    
    @staticmethod
    def intersection(b1,b2):
        (val1, len1) = boolprim.parsebool(b1)
        (val2, len2) = boolprim.parsebool(b2)
        return boolprim.tooct( val1 & val2, min(len1, len2) )
    
    @staticmethod
    def complement(b):
        (val, len) = boolprim.parsebool(b)
        return boolprim.tooct( boolprim.mask(len) & ~val, len )
    
    @staticmethod
    def rotate(d,b):
        n = mathprim.parsenum(d)[0]
        (val, len) = boolprim.parsebool(b)
        nbits = len * 3
        rotleft = n % nbits
        return boolprim.tooct( (val<<rotleft & boolprim.mask(len))
             | val>>(nbits-rotleft), len )

    @staticmethod
    def shift(d,b):
        n = mathprim.parsenum(d)[0]
        (val, len) = boolprim.parsebool(b)
        if n >= 0:
            return boolprim.tooct ( (val << n) & boolprim.mask(len) if n<len*3 else 0, len)
        else:
            n = -n
            return boolprim.tooct(  val >> n if n < len*3 else 0, len )

def parse(active):
    """parse(active) recursively scans an 'active string' of characters as 
    input.  It returns a triple (neutral, delim, tail), where neutral is the 
    list of characters which result from parsing the string up to the 
    separator character sep, which is ',' or ')', and tail is the remaining 
    active string.  When it finds #( or ##(, it recursively calls itself and 
    then calls eval to evaluate the expression.  It also handles 'protected' 
    strings (which are surrounded by parentheses).  Handily, you can call it 
    from the Python command line: trac.parse('#(ln, )')"""
    
    global syntchar
    depth = 0   # how many (s
    neutral = ''   # output so far
    while True:
        match = syntchar.getre().search(active)
        if match == None: return (neutral+active, '', '')
        ch = match.group()
        neutral += active[0:match.start()]
        active = active[match.end():]      # which had better be match.start()+1
        if ch == '(':
            if depth > 0: neutral += ch     #already protected, add it
            depth+=1
            continue
        if depth > 0:
            if ch == ')':
                depth -= 1
                if depth == 0: continue         #ends protection
            neutral += ch     # anything else in a protected string
            continue
        
        #depth = 0, so active parsing
        if ch == '\n': continue     #strip unprotected 'returns'
        if ch == ',' or ch == ')':
            return (neutral, ch, active)
        if ch == syntchar.get():
            if active[0] == '(':
                activefn = True      #active function: #(...)
                active = active[1:]
            elif active[0:2] == ( ch + '(' ):   # ch is equal to the syntchar
                activefn = False    #neutral function: ##(...)
                active = active[2:]
            else:   # not a call, just a random syntax character
                neutral += ch
                continue
            #OK, it's a call, gather the arguments
            args = []
            while True:
                (arg, delim, active) = parse(active)
                args.append(arg)
                if delim == ',': continue
                if delim == ')':
                    (result, activefn) = eval(args, activefn)
                    if activefn:
                        active = result + active
                    else:   # 'neutral'
                        neutral +=result
                    break   # we executed the call
                if delim == '':
                    raise tracError(False, "<UNF> hit end of string while expecting ')'")
                assert False    #unexpected delimiter
            continue    # if you get here, the call has been executed, continue parsing
        assert False    # unrecognized match to syntre

def eval(arglist, act):     # when a function call is assembled by the parser, this executes
    global activeImpliedCall
    if trace():
        s = syntchar.get()
        ourOS.print_(s+'/' if act else s+s+'/',arglist[0],end=' ')
        for a in arglist[1:]:
            ourOS.print_('*',a,end=' ')
        ourOS.print_('/',end=' ')
        input = sys.stdin.readline()
        if input != '\n':
            trace(False)
            raise KeyboardInterrupt
    pname = arglist[0].lower()
    if pname in prims:
        p = prims[pname]
        if Mode.extprim() or not p.extended:
            val = prims[pname](*arglist[1:])
            #if val == None: val = ''
            if isinstance(val,str): return (val, act)
            if isinstance(val,tuple):    # some prims force active "default" argument
                assert len(val) == 2
                return (val[0], act or val[1])  #val[1] forces active for "default call"
            return ('',act)     #ds, for example returns the 'form' type; throw it away
            #cm returns a boolean
    # here if it's not a primitive, or if it is an extended primitive not running in
    # extended mode
    activeImpliedCall = act
    return ( prims['cl'](*arglist), True )

prims = {}      # dict of the 'primitives'

# these are the primitives, pretty much in the order of Mooers spec

prim( 'ps', ( lambda x: tc.printstr(x) ), exact=1 )
# tc can change, so need to do it this way

prim( 'rs', ( lambda *a: tc.readstr(*a) ) )     # extended form of RS 1/11/15

prim( 'cm', ( lambda x: metachar.set(x,syntchar.get()) ), exact=1 )

prim( 'rc', ( lambda: tc.readch() ), exact=0 )

prim( 'ds', form, exact=2)

prim( 'dd', ( lambda *a: form.deletedef(*a) ) )

prim( 'da', ( lambda: form.deleteall() ), exact=0 )

prim( 'ss', ( lambda x, *a: form.find(x).segment(*a) ), minargs=1 )

prim( 'cl', ( lambda x, *a: form.find(x).val(*a) ), minargs=1 )

# "neutral implied" via C.A.R. Kagan
prim( 'ni', ( lambda x,y: y if activeImpliedCall else x ), minargs=1, \
    maxargs=2, extended=True )

prim( 'cr', ( lambda x: form.find(x).resetPointer() ), exact=1 )

prim( 'cc', form.callCharacter, minargs=1, maxargs=2 )

prim( 'cs', form.callSeg, minargs=1, maxargs=2 )

prim( 'cn', form.callN, minargs=2, maxargs=3 )

prim( 'in', form.initial, minargs=2, maxargs=3 )

mathprim( 'ad', ( lambda x,y: x + y ), minargs=2, maxargs=3 )

mathprim( 'su', ( lambda x,y: x - y ), minargs=2, maxargs=3 )

mathprim( 'ml', ( lambda x,y: x * y ), minargs=2, maxargs=3 )

mathprim( 'dv', ( lambda x,y: x // y ), minargs=2, maxargs=3 )

mathprim( 'rm', ( lambda x,y: x % y ), minargs=2, maxargs=3, extended=True )

prim( 'bu', boolprim.union, exact=2 )

prim( 'bi', boolprim.intersection, exact=2 )

prim( 'bc', boolprim.complement, exact=1 )

prim( 'br', boolprim.rotate, exact=2 )

prim( 'bs', boolprim.shift, exact=2 )

prim( 'eq', ( lambda x, y, z, w: z if (x==y) else w ), minargs=3, maxargs=4 )
# don't allow :()more than 4 args, but if fewer, supply null strings

prim( 'gr', ( lambda x, y, z, w: z if ( mathprim.tracint(x) > \
    mathprim.tracint(y) ) else w ), minargs=3, maxargs=4 )

prim( 'sb', block.store )

prim( 'fb', block.fetch )

prim( 'eb', block.erase )

prim( 'ln', ( lambda x: x.join(forms) ), exact=1 )

prim( 'pf', ( lambda x: ourOS.print_(form.find(x)) ), exact=1 )

prim( 'tn', ( lambda: trace(True) ), exact=0 )

prim( 'tf', ( lambda: trace(False) ), exact=0 )

prim( 'hl', tracHalt, exact=0 )

prim( 'mo', Mode.setmode )

def main(*args):
    global syntchar, forms, metachar, activeImpliedCall, tracing
    global ourOS, tc, rshistory
    try:
        ourOS = TheOS.whichOS()
    except termError as e:  # misformatted ansicon string can throw error
        print('Error:', str(e))
    rshistory = []
    forms = {}      # the defined strings
    syntchar = syntclass('#')
    metachar = specchar("'")
    activeImpliedCall = False   # in case there is a call to NI before an implied call
    trace(False)
    tc = None   # because setcontype saves this for error recovery
    for x in args:
        try:
            if x == '-mo':
                Mode.setmode()
            elif len (x)>4 and x[0:4] == '-mo,':
                Mode.setmode( *(x[4:].split(',')) )
            else:
                print('Error: unrecognized paramater (',x,')')
        except primError as e:
            print( 'Error:', ''.join(map(str,e[1:])) )
    if tc == None:  #default console type by OS, if not set by switches
        Mode.setcontype(ourOS.defaultterm())
    psrs()

def psrs():     # the main loop
    #global syntchar
    while True:
        strpsrs = syntchar.get() + '(ps,' + syntchar.get() + '(rs))'
        tc.printstr(strpsrs+'\n> ')
        try:
            remainder = ''.join( parse(strpsrs) )
            ourOS.print_('')    #blank line
            if remainder != '':
                raise tracError(False, '<UNF> unbalanced parens: ' \
                    'after parsing, remainder = ' + remainder)
        except tracHalt:            # terminate: HL or EOF (^D)
            return
        except tracError as e:
            if Mode.unforgiving() or e.args[0]:
                ourOS.print_( str(e) )
            else:
                ourOS.print_( '' )
        except termError as e:
            ourOS.print_( str(e) )
        except KeyboardInterrupt:   # ^C or non-empty input while trace on
            ourOS.print_('<INT>')
        except RuntimeError as e:   # mostly recursion depth exceeding (e.g #(fact,1000) )
            ourOS.print_( '<SCE>', str(e) )
        finally:            # for debugging, OK to comment out
            for f in forms: forms[f].validate()

if __name__ == '__main__': main(*sys.argv[1:])
