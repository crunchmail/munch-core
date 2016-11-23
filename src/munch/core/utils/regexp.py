import re

# from https://mail.python.org/pipermail/tutor/2002-February/012481.html

urls = '(%s)' % '|'.join("http https ftp".split())
ltrs = r'\w'
gunk = r'/#~:.?+=&%@!\-'
punc = r'.:?\-'
any = "%s%s%s" % (ltrs, gunk, punc)

url = r"""
    (                             # begin \1 {
        %(urls)s    :             # need resource and a colon
        [%(any)s] +?              # followed by one or more
                                  #  of any valid character, but
                                  #  be conservative and take only
                                  #  what you need to....
    )                             # end   \1 }
    (?=                           # look-ahead non-consumptive assertion
            [%(punc)s]*           # either 0 or more punctuation
            [^%(any)s]            #  followed by a non-url char
        |                         # or else
            $                     #  then end of the string
    )
    """ % {'urls': urls,
           'any': any,
           'punc': punc}

url_re = re.compile(url, re.VERBOSE)
mkd_footnote_url_re = re.compile(
    r'(?P<fnmark>\[\d+\]\:)\s(?P<url>{})'.format(url), re.VERBOSE)
