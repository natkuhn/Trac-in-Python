#! /usr/bin/env python

# trac processor (Mooers' T-64)
# Nat Kuhn (NSK), 7/5/13, v1.0  7/25/13

"""This Trac processor implements Calvin N. Mooers T-64 standard, as described in his
1972 document (http://web.archive.org/web/20050205173449/http://tracfoundation.org/t64tech.htm)

There are a few deviations:
1. Trac input terminates with a "meta character" (default '), and Trac is supposed to spring
into action as soon as you hit it.  This implementation reads from stdin, which waits for
an <enter> before sending text along.  So you need to hit <enter> after '.  The <enter>
is stripped out if it immediately follows the meta character.  If <enter> is the meta 
character, there is no problem.  #(rc) actually reads a single character. #(rs) could be 
implemented in the same way, except that it's hard to implement backspace and VERY 
difficult to paste stuff in.  Any intrepid soul who wishes to implement this with CURSES
would be considered excellent.

2. In the Mooers standard, the storage primitives (fb,sb,eb) store a "hardware address" of 
the storage block in a named form.  I could have slavishly followed this, putting the file
name in a form, but instead, you just supply the file name as the argument, e.g. 
#(fb,fact.trac)' gets the forms in a file "fact.trac" rather than from an address (filename)
stored in the form named fact.trac

3. I stuck some extra spaces in the trace (#(TN)) output for readability

4. There are a couple extra primitives:

4a.  #(rm,a,b,default) is a "remainder" function, returns a mod b, and the default arg for
dividing by 0, just as in DV

4b. NI (neutral implied) #(ni,a,b) returns a if the last implied call ("default call")
was neutral.  This allows scripts to function more like true primitives.  For example:

#(ds,repeat,(#(eq,*2,0,,(#(ni,#)#(cl,*1)#(cl,repeat,*1,#(su,*2,1))))))'
#(ss,repeat,*1,*2)'
#(ds,a,(#(ps,hello)))'
#(repeat,a,5)'
hellohellohellohellohello
##(repeat,a,5)'
#(ps,hello)#(ps,hello)#(ps,hello)#(ps,hello)#(ps,hello)

NI was described to me by Claude Kagan, and I always thought it was part of the T-64 
standard, but it's not in the Mooers document cited above.  I have no idea whether the
idea came from Claude, Mooers, or somewhere else.  Presumably not from Mooers, because 
he used the term "default call" while Claude used the term "implied call."

5. See extensions to MO in the mode class.

6. I have also added an 'unforgiving' mode #(mo,e,u) turns it on and #(mo,e,-u) turns it
off.  It generates error messages and terminates scripts for things such as 'form not
found', 'too many arguments', 'too few arguments' etc.  Per Mooers extra arguements should
be ignored, missing arguments filled with null strings (with few exceptions such as the 
block primitives).  There may be a few scripts that depend on this feature.  In any case,
it is turned off as a default.

7. The "up arrow" (shift-6 on the teletype) was replaced by the caret probably in the 
early 1970s.  I use the caret in PF, though with this new-fangled unicode stuff you could
probably manage a real up-arrow.  :-/

Thanks to Ben Kuhn for getting me Hooked on Pythonics, and to John Levine for consultation,
stimulation, and general interest.

There are undoubtedly many bugs; I just found a huge one in v0.9.  Let me know, I'll fix
them!

Nat Kuhn (NSK, nk@natkuhn.com)
"""

# v1.0 moves the _Getch code into the main module so it all runs out of a single file
# v0.9 fixes a bug in which seg gaps were identical objects, leading to multiple form
# pointers in a single form. Trace implemented per Mooers
# v0.8 cleans up MO, adds STE error, makes RC functional, traps ^C, implements booleans,
#   implements IN.  Complete T-64
# v0.7 cleans up error handling, changes "padto" and "exact" for primitive arguments
#   to "minargs" and "maxargs".  Implements MO
# v0.6 major change is adding endchunk(), eliminating corner cases; partial call
#   primitives now work

# Sample scripts:

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
import re
import sys
import cPickle as pickle                # for SB and FB
import os                               # for EB

# these four _Getch classes make #(rc) work; the awesome code is from 
# http://code.activestate.com/recipes/134892/
# special thanks to C Smith for the Mac OS code addition

class _Getch:
    """Gets a single character from standard input.  Does not echo to the
screen."""
    def __init__(self):
        try:
            self.impl = _GetchWindows()
        except ImportError:
            try:
                self.impl = _GetchMacCarbon()
            except ImportError, AttributeError:
                self.impl = _GetchUnix()

    def __call__(self): return self.impl()

class _GetchMacCarbon:
    """
    A function which returns the current ASCII key that is down;
    if no ASCII key is down, the null string is returned.  The
    page http://www.mactech.com/macintosh-c/chap02-1.html was
    very helpful in figuring out how to do this.
    """
    def __init__(self):
        import Carbon
        Carbon.Evt #see if it has this (in Unix, it doesn't)

    def __call__(self):
        import Carbon
        if Carbon.Evt.EventAvail(0x0008)[0]==0: # 0x0008 is the keyDownMask
            return ''
        else:
            #
            # The event contains the following info:
            # (what,msg,when,where,mod)=Carbon.Evt.GetNextEvent(0x0008)[1]
            #
            # The message (msg) contains the ASCII char which is
            # extracted with the 0x000000FF charCodeMask; this
            # number is converted to an ASCII character with chr() and
            # returned
            #
            (what,msg,when,where,mod)=Carbon.Evt.GetNextEvent(0x0008)[1]
            return chr(msg & 0x000000FF)

class _GetchUnix:
    def __init__(self):
        import tty, sys, termios # import termios now or else you'll get the Unix version on the Mac

    def __call__(self):
        import sys, tty, termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

class _GetchWindows:
    def __init__(self):
        import msvcrt

    def __call__(self):
        import msvcrt
        return msvcrt.getch()

# and now back to NSK code for the Trac Processor

class form:
    """a 'form' is a 'defined string.' It is stored as a list; each element in the list 
    is a 'formchunk': either a 'textchunk,'  a 'gapchunk,' or an 'endchunk'
    The 'form pointer' falls between characters or between a character and a segment
    gap.  'pointerchunk' is an int that tells which chunk the form pointer lies in.
    A chunk c has a field, c.pointer, that is -1 if the form pointer is outside the 
    chunk, and >= if inside (i.e. the chunk is 'active'.  exitchunk and enterchunk handle
    this bookkeeping.
    
    In a textchunk, the pointer can only be to the left of a character; if it's at the
    right end of the chunk, it must actually be at the start of the next chunk.  Hence,
    if the pointer is at the 'far right' of the form, chunkp points to the terminating
    endchunk."""
    
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
        """form.validate() makes sure that a form is valid.  The main loop (psrs(), below)
        checks each form every time through.  I caught some bugs this way I might not have
        otherwise."""
        activecount = 0 # chunks with c.pointer>=0, all but 1 chunk should have -1.
        endcount = 0    # endchunks
        previstext = False  # if the previous chunk was text (can't have two in a row)
        invalid = False
        for c in self.formlist:
            if c.pointer >= 0: activecount += 1
            if isinstance(c, textchunk):
                if previstext:
                    print('Invalid form: consecutive text chunks in', self.name, \
                        ':',c.text,'and previous')
                    invalid = True
                previstext = True
                if (c.text) == '':
                    print('Invalid form: null text chunk in',self.name)
                    invalid = True
                if c.pointer >= len(c.text) or c.pointer <-1:
                    print('Invalid pointer (',c.pointer,') in text chunk',c.text)
                    invalid = True
                continue
            previstext = False  #segment gap or end
            if c.pointer < -1 or c.pointer > 0:
                    print('Invalid pointer (',c.pointer,') in gapchunk or endchunk')
                    invalid = True
            if isinstance(c, endchunk): endcount+=1
        if activecount != 1:
            print('Invalid form:',activecount,'active chunks in',self.name)
            invalid = True
        if endcount != 1:
            print('Invalid form: endcount (',endcount,') is illegal in',self.name)
            invalid = True
        if not isinstance(self.formlist[len(self.formlist)-1], endchunk):
            print('Invalid form: endchunk not at end of',self.name)
            invalid = True
        if invalid: print('Invalid form',self.name, ': [', *self.formlist)
        
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
                if mode.unforgiving: form.FNFError(name)
    
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
        return ('<^>' if self.pointer == 0 else '') + '<'+str(self.gapno+1)+'>'
        #oops, trac segment gaps are 1-based, not 0-based!
    
class endchunk(formchunk):
    """this chunk needs to go at the end of every form; when the form pointer is at
    the end (right-hand end) of a form, chunkp points to this chunk.  Many corner cases
    are eliminated by having it."""
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


class tracconsole:
    def __init__(self):
        self.charbuf = ''
        self.inkey = _Getch()
    
    def readch(self):
        ch = self.inkey()   # TODO check for ^D? ^C?
        code = ord(ch)
        if code == 3: raise KeyboardInterrupt   # ^C
        print(ch, end='')
        return ch
    
    def readstr(self):
        """New, improved readstr function. Rather than using stdin.readline(), loops on
        getch(); this allows it to capture the metacharacter immediately, rather than
        waiting for a newline. If it receives a backspace, it types over the previous
        character, so everything looks normal. Works fine with copy-paste too.

        Known issues:
        1. Screws up backspacing when the line is long enough to get soft-wrapped by the
        terminal. Not implemented because I don't know the how the original TRAC behaved
        in this circumstance.
        2. Can't backspace over user-inserted newlines either (ditto).
        3. Does not have nice GNU-readline-ish features like paren matching, ^H for
        backspace, history, etc. Could be implemented depending on how much of a TRAC
        purist you are.

        Unknown issues: Lots. Still needs more extensive testing."""
        string = ''
        mc = metachar.get()
        while True:
            ch = self.inkey()
            code = ord(ch)
            if code == 3: # ^C
                raise KeyboardInterrupt
            elif code == 4:
                raise tracHalt
            elif code == 127: # backspace
                # print a space over the character immediately preceding the cursor
                # but we can't backspace over newlines
                if string[-1] != '\n':
                    print('\b \b', end='')
                    string = string[:-1]
            elif code == 13:
                string += '\n'
                print()
            else:
                print(ch, end='')
                if ch == mc:
                    return string
                else:
                    string += ch
    
tc = tracconsole()

class specchar:
    """a container for the 'meta character' which terminates #(RS), and the 'syntax 
    character (default, #), which is not changeable in the T-64 spec, but which Claude
    Kagan used as :.  It can be changed with #(mo,ms,x) which is how John Levine 
    remembers it, and I think he's right"""
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
            return False
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
    
class block:        # handles the block primitives.  a static class
    @staticmethod
    def store(*args):           # for SB
        if len(args) == 0: prim.TFAError(0,1,True)   # expecting 1 or more
        sblist = []
        for n in args[1:]:
            if n in forms:
                f = forms[n]    #can't use form.find b/c it terminates if not found
                if f not in sblist: sblist.append(f)
            else:
                if mode.unforgiving: form.FNFError(n)
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
        if mode. unforgiving and l > 1: prim.TMAError(l,1)
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
        if mode. unforgiving and l > 1: prim.TMAError(l,1)
        try:
            os.remove(args[0])
        except OSError as e:
            raise tracError(True, '<STE> ',e)
    
class tracHalt(Exception):  # used for HL and for EOF (^D) on stdin
    def __init__(self):
        raise self

class tracError(Exception):
    """the first of the args is True if the error message is to be given even
    when mode.unforgiving is False.  The other args are joined together to form the 
    message.  As of now the only use for the True setting is the <STE> errors"""
    
    def __str__(self):
        return ''.join(map(str,self.args[1:]))
    
class primError(Exception):
    """this is for 'primitive errors.'  The first of the args is False if the primitive
    should simply abort and return a null value unless mode.unforgiving is True, in
    which case execution will stop and the message will be displayed.  If the first arg
    is True, execution is halted and the message is displayed no matter what."""
    pass
    
class mode:     # for MO
#must be defined above primitives, in case there is a duplicate
    extended = True
    unforgiving = False
    
    @staticmethod
    def setmode(*args):
        """#(mo) goes into T-64 regulation mode. #(mo,e) allows extended primitives
        such as #(rm,5,2).  #(mo,e,switches) allows +/- p for extended primitives, and
        +/- u for unforgiving errors, e.g. no extended primitives but unforgiving errors
        is #(mo,e,+p-u).  #(mo,pm) prints out the current mode switches.
        #(mo,ms,:) modifies the syntactic character, in this case to ':', following
        C.A.R. Kagan... apparently this was easier to type on a Teletype; it's no easier
        on a standard keyboard, so I switched to the # camp... especially since you
        can put scripts in as Python comments, and not have to edit out initial #s.
        NSK"""
        
        # if you wanted to add more switches, you could clean up this code and automate
        # some of it
        
        if len(args) == 0:  # #(MO): meet the T-64 spec
            mode.extended = False   #no extra primitives
            mode.unforgiving = False    #don't throw errors re: wrong # of args, FNF etc
            return
        modearg = args[0].lower()
        if modearg == 'ms':    # C. A. R. Kagan extension to Modify Syntax character
            syntchar.set( '' if len(args) == 1 else args[1], metachar.get() )
            return
        if modearg == 'pm':
            print('<MO>: ' + ('' if mode.extended else 'un') + 'extended primitives; ' + \
                ('un' if mode.unforgiving else '') + 'forgiving with errors.', end='')
            return
        if modearg == 'e':
            if len(args) == 1:
                mode.extended = True
                return
            else:
                switches = args[1]
                while switches != '':
                    val = True
                    if switches[0] == '+': switches = switches[1:]
                    elif switches[0] == '-':
                        val = False
                        switches = switches[1:]
                    if switches == '':
                        raise primError(False, 'missing switch')
                    if switches[0] == 'p':      #extended primitives
                        mode.extended = val
                        switches = switches[1:]
                        continue
                    if switches[0] == 'u':      #unforgiving errors
                        mode.unforgiving = val
                        switches = switches[1:]
                        continue
                    raise primError(False, 'unrecognized switch: ', switches[0] )
                return
        raise primError(False, 'unrecognized mode: ', modearg)
    
def trace(*args):       # a flag, used in TN and TF
    global tracing
    if len(args) == 0:
        return tracing
    else:
        tracing = args[0]
        return

class prim:
    """each 'primitive' is an instance of this class, or its active subclass mathprim
    """
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
            if mode.unforgiving or p.args[0]:   #interrupt execution
                raise tracError(True, '<UNF> (', self.name, ') ',*p.args[1:])
            else:
                return ''
        if val == None: return ''
        else: return val
    
    def fixargs(self,*args):    #pads if necessary, and checks too many or too few
        l = len(args)
        if mode.unforgiving:
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
    def TMAError(has,expecting):
        raise primError(False, 'too many arguments: has ',has,', expecting ', expecting)
    
    @staticmethod
    def TFAError(has,expecting,ormore):
        raise primError(False, 'too few arguments: has ',has,', expecting ', expecting, \
            ' or more' if ormore else '')
    
class mathprim(prim):   # for AD, SU, ML, DV, RM
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
        """returns (signed numerical part, prefix part, sign) as per p.53 of Mooers [1972]
        note that CN distinguishes -0 from 0...."""
        m = mathprim.numre.match(arg)
        unsignedstr = m.group(3)
        u = 0 if unsignedstr=='' else int(unsignedstr)
        sign = m.group(2)
        return ( -u if sign=='-' else u, m.group(1), sign )
    
    @staticmethod
    def tracint(x):     # used above, and also in GR
        return mathprim.parsenum(x)[0]

mathprim.numre = re.compile(r'^(.*?)([+-]?)([0-9]*)\Z',re.DOTALL) #initial ^ is redundant for match

class boolprim(prim):
    """this is really a class for static methods, not one we create instances of"""
    
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

    
boolprim.boolre = re.compile(r'([0-7]*)\Z')

def parse(active):
    """parse(active) recursively scans an 'active string' of characters as input.
    It returns a triple (neutral, delim, tail), where neutral is the list of characters
    which result from parsing the string up to the separator character sep, which is 
    ',' or ')', and tail is the remaining active string.  When it finds #( or ##(,
    it recursively calls itself and then calls eval to evaluate the expression.
    It also handles 'protected' strings (which are surrounded by parentheses).
    Handily, you can call it from the Python command line:
    trac.parse('#(ln, )')"""
    
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
        print(s+'/' if act else s+s+'/',arglist[0],end=' ')
        for a in arglist[1:]:
            print('*',a,end=' ')
        print('/',end=' ')
        input = sys.stdin.readline()
        if input != '\n':
            trace(False)
            raise KeyboardInterrupt
    pname = arglist[0].lower()
    if pname in prims:
        p = prims[pname]
        if mode.extended or not p.extended:
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

prim( 'ps', ( lambda x: print(x,end='') ), exact=1 )

prim( 'rs', tc.readstr, exact=0 )

prim( 'cm', ( lambda x: metachar.set(x,syntchar.get()) ), exact=1 )

prim( 'rc', tc.readch, exact=0 )

prim( 'ds', form, exact=2)

prim( 'dd', ( lambda *a: form.deletedef(*a) ) )

prim( 'da', ( lambda: form.deleteall() ), exact=0 )

prim( 'ss', ( lambda x, *a: form.find(x).segment(*a) ), minargs=1 )

prim( 'cl', ( lambda x, *a: form.find(x).val(*a) ), minargs=1 )

# "neutral implied" via C.A.R. Kagan
prim( 'ni', ( lambda x,y: y if activeImpliedCall else x ), minargs=1, maxargs=2, extended=True )

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

prim( 'gr', ( lambda x, y, z, w: z if ( mathprim.tracint(x) > mathprim.tracint(y) ) \
    else w ), minargs=3, maxargs=4 )

prim( 'sb', block.store )

prim( 'fb', block.fetch )

prim( 'eb', block.erase )

prim( 'ln', ( lambda x: x.join(forms) ), exact=1 )

prim( 'pf', ( lambda x: print(form.find(x)) ), exact=1 )

prim( 'tn', ( lambda: trace(True) ), exact=0 )

prim( 'tf', ( lambda: trace(False) ), exact=0 )

prim( 'hl', tracHalt, exact=0 )

prim( 'mo', mode.setmode )

def main():
    global syntchar, forms, metachar, activeImpliedCall, tracing
    forms = {}      # the defined strings
    syntchar = syntclass('#')
    metachar = specchar("'")
    activeImpliedCall = False   # in case there is a call to NI before an implied call
    trace(False)
    psrs()

def psrs():     # the main loop
    global syntchar
    while True:
        strpsrs = syntchar.get() + '(ps,' + syntchar.get() + '(rs))'
        print(strpsrs+'\n> ', end='')
        try:
            remainder = ''.join( parse(strpsrs) )
            print('')    #blank line
            if remainder != '':
                raise tracError(False, \
                    '<UNF> unbalanced parens: after parsing remainder = ' + remainder)
        except tracHalt:            # terminate: HL or EOF (^D)
            return
        except tracError as e:
            if mode.unforgiving or e.args[0]:
                print( str(e) )
        except KeyboardInterrupt:   # ^C or non-empty input while trace on
            print('<INT>')
        except RuntimeError as e:   # mostly recursion depth exceeding (e.g #(fact,1000) )
            print( '<SCE>', str(e) )
        finally:
            for f in forms: forms[f].validate() # for debugging, OK to comment out

if __name__ == '__main__': main()
