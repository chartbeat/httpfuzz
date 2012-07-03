#!/usr/bin/python
"""
Utility for replaying request logs that were generated with fuzz.py
"""

import sys
import json
import binascii
import functools
from optparse import OptionParser
from cmd import Cmd

from network import SocketHTTP


def getdoc(obj):
    """Gets the docstring and removes leading whitespace"""
    docstring = obj.__doc__
    if not docstring:
        return ''
    # Convert tabs to spaces (following the normal Python rules)
    # and split into a list of lines:
    lines = docstring.expandtabs().splitlines()
    # Determine minimum indentation (first line doesn't count):
    indent = sys.maxint
    for line in lines[1:]:
        stripped = line.lstrip()
        if stripped:
            indent = min(indent, len(line) - len(stripped))
    # Remove indentation (first line is special):
    trimmed = [lines[0].strip()]
    if indent < sys.maxint:
        for line in lines[1:]:
            trimmed.append(line[indent:].rstrip())
    # Strip off trailing and leading blank lines:
    while trimmed and not trimmed[-1]:
        trimmed.pop()
    while trimmed and not trimmed[0]:
        trimmed.pop(0)
    # Return a single string:
    return '\n'.join(trimmed)


def defaultarg(f):
    """Decorator for handlers with a default argument"""
    @functools.wraps(f)
    def g(self, args):
        return f(self, args) if args else f(self)
    return g


class SimpleHandler(Cmd, object):

    class DefaultArger(type):
        """Metaclass which decorates all do_* methods with defaultarg"""

        def __new__(mcs, name, bases, d):
            for k, v in d.items():
                if k.startswith('do_'):
                    d[k] = defaultarg(v)
            return type.__new__(mcs, name, bases, d)

    __metaclass__ = DefaultArger

    def do_help(self, command=None):
        """Display the help"""
        if command is None:
            # print all the commands with a 1 line summary from the docstring
            commands = [x[3:] for x in dir(self.__class__) if x.startswith('do_')]
            maxlen = max(len(x) for x in commands)
            print '\nAvailable Commands:'
            for c in commands:
                doc = getattr(self, 'do_' + c).func_doc or ''
                doc = doc.split('\n')[0]
                print '{0}{1}    {2}'.format(c, ' '*(maxlen - len(c)), doc)

            doc = getdoc(self.default)
            if doc:
                doc = '\n'.join([' '*4 + x for x in doc.split('\n')])
                print '\nIf no command is specified:\n', doc
            print '\nPressing enter will repeat the previous command.'
        else:
            # print the docstring, if it exists
            f = getattr(self, 'do_' + command, None)
            if f is None:
                print 'Command {0} does not exist'.format(command)
                return
            print '\n', getdoc(f), '\n'

    def do_EOF(self):
        """Exit the command loop"""
        print
        return True


class REPLHandler(SimpleHandler):
    def __init__(self, requests, http):
        SimpleHandler.__init__(self)
        self._requests = requests
        self._http = http
        self._cur = 0

    def do_n(self, args=1):
        """Send the next request(s)

        Accepts a positive integer argument: how many requests to send (default 1)
        """
        try:
            limit = int(args)
        except Exception:
            print 'Invalid argument {0}, must be an integer'.format(args)
            return

        reqs = self._requests[self._cur:self._cur+limit]

        sent = 0
        for req in reqs:
            self._http.send_request(req['request'])
            self._cur += 1
            sent += 1

        print 'Sent {0} requests. {1}/{2} left'.format(sent,
                                                       max(0, len(self._requests) - self._cur),
                                                       len(self._requests))

    def do_r(self):
        """Start over."""
        self._cur = 0

    def do_p(self, args=1):
        """Print n requests."""

        try:
            num = int(args)
        except Exception:
            print 'Invalid argument {0}. Integer expected.'.format(args)

        for i in xrange(self._cur + min(0, num), self._cur + max(0, num)):
            req = self._requests[i]
            print req['request'].__repr__()

    default = do_n


def main():
    parser = OptionParser()
    parser.add_option('--host', default='localhost:9080', help='HTTP server to which send the request')
    parser.add_option('--file', default='fuzzy_requests.log', help='File to replay')
    options, args = parser.parse_args()

    with open(options.file) as fd:
        content = fd.read()
        logs = json.loads(content)
        for i in xrange(len(logs)):
            logs[i]['request'] = binascii.a2b_base64(logs[i]['request'])

    http = SocketHTTP(options.host)

    print '{0} total requests.'.format(len(logs))
    print 'Type help for help. Ctrl-D to exit.'
    handler = REPLHandler(logs, http)
    handler.cmdloop()


if __name__ == '__main__':
    main()
