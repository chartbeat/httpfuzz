#!/usr/bin/python
"""
Utility for running fuzzy testing on http applications.
"""

from datetime import datetime
import logging
import random
import string
import binascii
import json
from optparse import OptionParser

from network import SocketHTTP


CHARS_ASCII = [ chr(i) for i in xrange(36, 127) ]
CHARS_LETTERS = string.letters
CHARS_ALL = [ chr(i) for i in xrange(0, 256) ]


VALID_OPS = (
    'set',
    'inc',
    'rand_int',
    'rand_str_ascii',
    'rand_str_all',
    'rand_str_letters',
    'prefix_rand_str_ascii',
)
"""
List of valid operation, for sanity checking test file
"""


def apply_op(current_value, conf):
    op = conf['op']

    if op not in VALID_OPS:
        raise Exception("Invalid operation '{0}'. Config: {1}".format(op, conf))

    if op == 'set':
        current_value = conf['initial']
    elif op == 'inc':
        current_value += conf.get('step', 1)
    elif op == 'rand_str_ascii':
        length = random.randint(conf.get('min', 1), conf['max'])
        current_value = ''.join([random.choice(CHARS_ASCII) for i in xrange(length)])
    elif op == 'rand_str_letters':
        length = random.randint(conf.get('min', 1), conf['max'])
        current_value = ''.join([random.choice(CHARS_LETTERS) for i in xrange(length)])
    elif op == 'rand_str_all':
        length = random.randint(conf.get('min', 1), conf['max'])
        current_value = ''.join([random.choice(CHARS_ALL) for i in xrange(length)])
    elif op == 'rand_int':
        current_value = random.randint(conf['min'], conf['max'])
    elif op == 'prefix_rand_str_ascii':
        length = random.randint(conf.get('min', 1), conf['max'])
        current_value = conf['prefix'] + ''.join([random.choice(CHARS_LETTERS) for i in xrange(length)])

    return current_value



def construct_initial_query(query_def):
    query = {}
    for key, conf in query_def.iteritems():
        query[key] = conf.get('initial', '')

    return query


def advance_query(query, query_def):
    for key, conf in query_def.iteritems():
        query[key] = apply_op(query[key], conf)

    return query


def construct_query(old_query, query_def):
    query = {}

    if old_query:
        query = advance_query(old_query, query_def)
    else:
        query = construct_initial_query(query_def)

    return query


def run_test(test, http):
    http.set_path(test['path'])
    http.set_protocol(test.get('protocol', 'HTTP/1.1'))
    http.set_method(test.get('method', 'GET'))

    query = {}
    for i in xrange(test['num_requests']):
        query = construct_query(query, test['query'])
        http.set_params(query)
        http.fetch()


class RequestLogger(object):
    def __init__(self, out_fd):
        self._first = True
        self._out_fd = out_fd

    def start(self):
        self._out_fd.write("[")

    def finish(self):
        self._out_fd.write("]")

    def callback(self, request):
        # I have to encode the requests because there might be binary data.
        record = {
            'request': binascii.b2a_base64(request['request']),
        }

        if not self._first:
            self._out_fd.write(",")

        self._out_fd.write(json.dumps(record))
        self._first = False


def main():
    parser = OptionParser()
    parser.add_option('--host', default='localhost:9080', help='The http host on which to run the tests (localhost:9080).')
    parser.add_option('--no-end-marker', dest='nomarker', default=False, action='store_false', help='Don\' append &_ at the end of the uri (False).')
    parser.add_option('--response', default=False, action='store_true', help='Wait for the server to respone (False).')
    parser.add_option('--testfile', default='fuzz_test.json', help='File that contains test cases (fuzz_test.json).')
    parser.add_option('--tests', default='', help='Comma separated list of test names.')
    parser.add_option('--dry', default=False, action='store_true', help='Dry run, don\'t actually make the requests.')
    parser.add_option('--list', default=False, action='store_true', help='List test cases.')
    parser.add_option('--output', default=None, help='Output file.')
    options, args = parser.parse_args()

    with open(options.testfile) as f:
        content = f.read()
        tests = json.loads(content)

    if options.list:
        print "Available tests cases:"
        print
        for test in tests['tests']:
            print "Name: {0}\nDescription: {1}".format(test['name'], test.get('description', ''))
            print "Path: {0}".format(test['path'])
            print "Query params: {0}".format(' '.join([ key for key in test['query'] ]))
            print

        return

    http = SocketHTTP(options.host, options.nomarker, options.response, options.dry)

    test_cases = options.tests
    if test_cases:
        test_cases = test_cases.split(',')

    if not options.output:
        options.output = 'fuzzy_requests_{0}.json'.format(datetime.today().strftime('%Y_%m_%d_%H_%M_%S'))

    with open(options.output, 'w') as out_fd:
        request_logger = RequestLogger(out_fd)

        http.set_callback(lambda req: request_logger.callback(req))

        request_logger.start()

        try:
            for test in tests['tests']:
                if test_cases:
                    if test['name'] in test_cases:
                        print "Running test {0}".format(test['name'])
                        run_test(test, http)
                else:
                    print "Running test {0}".format(test['name'])
                    run_test(test, http)
        except Exception as e:
            logging.exception(e)

        request_logger.finish()

if __name__ == '__main__':
    main()
