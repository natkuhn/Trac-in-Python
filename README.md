This Trac Processor (i.e., interpreter) implements Calvin N. Mooers Trac T-64
standard, as described in his 1972 "[Definition and Standard for Trac (R) T-64
Language](http://web.archive.org/web/20050205173449/http://tracfoundation.org/t64tech.htm)",
also know as RR-284. The same page has a link to a "beginner's manual" for Trac.

Clicking here will [run this Trac
processor](https://replit.com/@NatKuhn/Trac-in-Python) on [replit.com](https://replit.com). 
You can click here for [a bit of background and an explanation of the example 
scripts](https://familykuhn.net/nat/trac). For a more long-winded history and recollections,
see my [blog post about this project](http://nats-tech.blogspot.com/2013/07/the-land-of-trac.html).

The GitHub home page for this project is https://github.com/natkuhn/Trac-in-Python. If
you are looking at this file on that page, you can download the file
archive just by clicking the "Download ZIP" button in the right-hand sidebar.

This archive contains: this README file, and the trac.py source code. I have
also included a few sample scripts. Try typing:

```
#(fb,fact.trac)#(fact,5)'
```

The program runs well under Python 2.7, and I tried to make it as compatible
with Python 3 as possible, but as of January 2020 it crashes in Python 3,
and there may be additional problems in
terms of how unicode-friendly it isn't. I have successfully run it on Mac OS
X, where it was developed, and on Windows. It should also run on Linux, but I
haven't tried it yet.

If you don't have Python 2.7 on your computer, you will need to [download it](https://www.python.org/downloads/release/python-278/).

Then, you will need to be at a command line ("Command Prompt" on Windows,
Terminal on Mac OS). Typing `python trac.py` will hopefully get you started.
To exit, type `#(hl)'` (the "Halt" primitive), or generate an end-of-file (^D on
Mac OS/Linux, ^Z on Windows). I was able to double-click the "trac.py" file
in Windows, and it worked.

On Mac and Linux it will use an enhanced input interface with cursor keys,
command history, etc (see below). To use this on Windows (which I highly
recommend), you have to download a program called ANSICON, or use the Unix-
like environment Cygwin (www.cygwin.org). For more on ANSICON, see below. If
you want to run it in Cygwin, you need to install the Cygwin python package;
it will not run in Windows-native Python under Cygwin.

There are a few deviations from the Mooers standard, including some
improvements:

1. In the Mooers standard, the storage primitives (`fb`,`sb`,`eb`) store a "hardware
   address" of the storage block in a named form. I could have slavishly followed
   this, putting the file name in a form, but instead, you just supply the file
   name as the argument, e.g. `#(fb,fact.trac)'` gets the forms in a file
   "fact.trac" rather than from an address (filename) stored in the form named
   `fact.trac`

2. I stuck some extra spaces in the trace (`#(TN)`) output for readability

3. There are a couple extra primitives:

- `#(rm,a,b,default)` is a "remainder" function, returns a mod b, and the
  default arg for dividing by 0, just as in `DV`

- NI (neutral implied) `#(ni,a,b)` returns a if the last implied call
  ("default call") was neutral. This allows scripts to function more like true
  primitives. For example:

```
#(ds,repeat,(#(eq,*2,0,,(#(ni,#)#(cl,*1)#(cl,repeat,*1,#(su,*2,1))))))'
#(ss,repeat,*1,*2)'
#(ds,a,(#(ps,hello)))'
#(repeat,a,5)'
hellohellohellohellohello
##(repeat,a,5)'
#(ps,hello)#(ps,hello)#(ps,hello)#(ps,hello)#(ps,hello)
```

NI was described to me by Claude Kagan, and I always thought it was part of
the T-64 standard, but it's not in the Mooers document cited above. I have
no idea whether the idea came from Claude, Mooers, or somewhere else.  
Presumably not from Mooers, because he used the term "default call" while
Claude used the term "implied call."

4.  The "up arrow" (shift-6 on the teletype) was replaced by the caret probably
    in the early 1970s. I use the caret in `PF`, though with this new-fangled
    unicode stuff you could probably manage a real up-arrow. :-/

5.  Terminal i/o: `#(mo,rt,term-mode)` allows you to set the terminal mode to
    `a`, `b`, or `l`. `#(mo,rt)` returns the current mode, in lower case. Incidentally,
    `rt` is for "reactive typewriter," Mooers' term for an interactive terminal.

- `l` (line-oriented i/o): uses sys.stdin.readline(), so that you need to hit
  `<enter>` before anything is actually read. Any newline immediately after a
  meta character is stripped out.

- `b` (basic terminal): implements a rudimentary backspace, which works back
  to the last newline, and then echoes deleted characters between
  backslashes. Default mode for Windows, has known issues. Based
  on code from Ben Kuhn.|

- `a` (ANSI terminal \[e.g., VT-100\] mode): default mode for Unix/Mac OS X;
  also works on Windows as described below. Works with backspace,
  delete, cursor up/down/left/right, and implements unix shell-style
  history using alt-left-arrow and alt-right-arrow (alt-up and
  alt-down on Windows). Shift-left- and right-arrow (alt-left and
  alt-right on Windows) move to beginning and end of the current
  line. I hope someone likes this because it was painful to
  implement! In ANSI mode, `#(mo,rt)` returns `a,switches,columns,rows`;
  to see those, you need to type `##(mo,rt)'`.

6.  In ANSI mode of #5 above, I have implemented an extended version of
    read string: #(rs,init string,displacement): it is as if the user has already
    entered 'init string' with the cursor placed at 'displacement'. If
    'displacement' is positive or `0` is is from the start of the string; if it is
    negative or `-0` it is from the end, i.e. `-0` positions the cursor at the very
    end of the string. This makes scripts like this one, to edit a form, possible:

```
#(ds,edit,(#(ds,**,##(rs,##(cl,**,<1>,<2>,<3>,<4>,<5>,<6>),-0))#(ss,**,<1>,<2>,<3>,<4>,<5>,<6>)))
#(ss,edit,**)
```

`#(edit,form)` then allows you to edit 'form'. Note you must move the cursor to
the end before you hit the meta character, otherwise it will get truncated.
Hitting down-arrow repeatedly is a quick way to move it to the end.

See more information on ANSI mode below.

7. I have also added an 'unforgiving' mode: `#(mo,e,u)` turns it on and
   `#(mo,e,-u)` turns it off. It generates error messages and terminates scripts
   for things such as 'form not found', 'too many arguments', 'too few arguments,'
   etc. Per Mooers extra arguments should be ignored, missing arguments filled
   with null strings (with few exceptions such as the block primitives). There
   may be a few scripts that depend on this feature. In any case, it is turned
   off as a default.

8. See other extensions to `MO` in the mode class in the source code.

Thanks to Ben Kuhn for getting me Hooked on Pythonics (and for getting me going
on improving `RS`); to John Levine for consultation, stimulation, and general
interest; and to Andrew Walker for his enthusiasm and support.

Please feel free to report bugs or request features!

Nat Kuhn (NSK, nk@natkuhn.com)

More information on ANSI terminal mode and ANSICON:

For ANSICON, see http://adoxa.altervista.org/ansicon/index.html.
Download the full package, use either the x86 (32-bit) or x64 (64-bit).
Double-click on ANSICON, and then enter `python trac.py -mo,rt,a`
(supplying the appropriate paths for the files, if necessary).

Known issue with the Windows Console: when you make the window narrower,
it doesn't wrap the lines at the new width, it just makes a scroll bar. As
a result I just leave the line width at buffer width. If you want a truly
narrower window, use Cygwin.

Shift-left and shift-right go to beginning and end of line (alt-left
and alt-right in Windows ANSICON).

Alt-left and Alt-right go backwards and forwards through history (alt-up
and alt-down in Windows ANSICON).

`#(mo,rt,a,switches,columns,rows)`

Switches (default is `+o+e+l`):

The first set of switches has to do with ascertaining the screen size. It
tries whichever of the the following methods are enabled (`o` and `e` by
default), in order, and uses the first successful one. If `+d` is enabled
it tries the other enabled modes and reports any discrepancies—mainly
useful for debugging:

- 'o': get screen size from OS (seems to work pretty universally)

- `t`: get screen size from polling the terminal using ESC sequences (works
  on OS X Terminal.app and not many others; prints garbage chars in ANSICON)

- `s`: get screen size from using 'tput' in subprocesses (supposedly
  necessary for cygwin using native Windows Python, but character-
  by-character I/O doesn't work under those circumstances anyway

- `e`: get screen size from environment variables (does not vary dynamically
  as user resizes screen, so a next-to-last resort)

- `f`: use fixed screen size, as set by columns, rows; default 80,25. These
  arguments can be present and they set the screen size for `+f`
  should it be activated in the future

- `d` report discrepancies from the above methods

The second set of switches has to do with ascertaining the location of
the cursor on the screen, mainly used to for figuring out when up-arrow
would go off top of screen (default is `+l`):

- `l` get screen location by polling the terminal
- `v` validate screen position and give error if it isn't correct (errors
  can be thrown by excessively fast typing, or by bug in ANSICON
  on Windows); again mainly for debugging

`#(mo,rt)` returns a,switches,cols,rows where cols,rows is the actual
reported size of the screen. Note that for all this to print you need
to use `##(mo,rt)`
