from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import pprint

""" Runs a basic server on port 8098

This server accepts POST requests and returns a 201, and logs the request to
stdout.
"""


class HTTPYesPostHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        print('Received POST')
        print(self.headers)

        length = int(self.headers['content-length'])
        data = self.rfile.read(length)
        try:
            pprint.pprint(json.loads(data.decode()))
        except Exception:
            print(data)

        self.send_response(201)
        self.end_headers()
        self.wfile.write(b'OK')


def run(
        server_class=HTTPServer,
        handler_class=BaseHTTPRequestHandler, port=8098):
    server_address = ('127.0.0.1', port)
    httpd = server_class(server_address, handler_class)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.socket.close()


if __name__ == '__main__':
    print('Running "always-yes" POST server on http://127.0.0.1:8098')
    server = run(port=8098, handler_class=HTTPYesPostHandler)
