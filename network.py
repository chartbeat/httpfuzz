import socket
import struct

class SocketHTTP(object):
    def __init__(self, host, nomarker=True, with_response=False, dry=False):
        if host.startswith("http://"):
            host = host[7:]
        elif host.startswith("https://"):
            host = host[8:]

        self._protocol = "HTTP/1.1"
        self._host = host
        self._fd = None
        self._params = {}
        self._path = '/'
        self._headers = {}
        self._method = 'GET'
        self._nomarker = nomarker
        self._with_response = with_response
        self._last_request = None
        self._dry = dry
        self._callback = None

    def set_callback(self, callback):
        self._callback = callback

    def set_protocol(self, protocol):
        self._protocol = protocol

    def set_method(self, method):
        self._method = method

    def set_headers(self, headers):
        self._headers = headers

    def set_path(self, path):
        self._path = path

    def set_params(self, params):
        self._params = params

    def last_request(self):
        return self._last_request

    def send_request(self, request, headers=None):
        host, port = self._host.split(':')
        fd = socket.create_connection((host, port))

        fd.send(request)

        #for key, value in headers.iteritems():
        #    if not self._dry:
        #        fd.send(struct.pack('sss', key, ": ", value))

        fd.send('\n\n')

        resp = None
        if self._with_response:
            resp = ''
            data = fd.recv(1024)
            while data:
                resp += data
                data = fd.recv(1024)

        fd.close()

        return resp

    def fetch(self):
        uri = str(self._path)
        uri = list(uri)

        if self._params or not self._nomarker:
            uri.append('?')

        if self._params:
            for key, value in self._params.iteritems():
                key = str(key)
                value = str(value)

                key = list(key)
                value = list(value)

                uri += key
                uri.append('=')
                uri += value
                uri.append('&')

        # Get rid of the trailing & in the query is any
        if uri[-1] == '&':
            uri = uri[:-1]

        if not self._nomarker:
            uri += list("&_")

        uri = bytearray(''.join(uri))
        uri = struct.pack("{0}B".format(len(uri)), *uri)

        request = "{0} {1} {2}".format(self._method, uri, self._protocol)

        self._last_request = {
            'request': request,
            'headers': self._headers,
        }

        if self._callback:
            self._callback(self._last_request)

        if self._dry:
            return None

        return self.send_request(request, self._headers)
