import datetime
import json
import os.path
import logging

import time
import multiprocessing as mp

import tornado.escape
import tornado.ioloop
import tornado.web
import tornado.websocket
import tornado.locks
import tornado.gen
from tornado.options import define, options, parse_command_line

from tornado.iostream import StreamClosedError

CHECK_INTERVAL = 1

define("port", default=8080, help="run on the given port", type=int)
define("debug", default=True, help="run in debug mode")
define("autoreload", default=True, help="run in debug mode")

lock = tornado.locks.Lock()


class TracertProcess(mp.Process):
    def __init__(self, queue):
        """
        Asynchronously parse tracert

        :param target: target address/name
        :param on_new_node: function to execute when new node is detected
        :return: return code (-1 = timeout, 0 = ok, 1 = command error, 2 = force terminated)
        """
        mp.Process.__init__(self)
        self.queue = queue

    def run(self):
        while True:
            while not self.queue.empty():
                data = self.queue.get_nowait()
                print("store data")


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("index.html")

"""
class GameDataBroadcastHandler(tornado.websocket.WebSocketHandler):
    def __init__(self, *args):
        super().__init__(*args)

    def open(self, *args):
        logging.info('GameDataBroadcast client connected')
        tornado.ioloop.IOLoop.instance().add_timeout(datetime.timedelta(seconds=CHECK_INTERVAL), self.check)

    def on_message(self, message):
        pass

    def on_close(self):
        logging.info('GameDataBroadcast client disconnected')

    def check(self):
        while not queue.empty():
            data = queue.get_nowait()
            #print(data)
            self.write_message(data)
        tornado.ioloop.IOLoop.instance().add_timeout(datetime.timedelta(seconds=CHECK_INTERVAL), self.check)
"""

class GameDataCollectHandler(tornado.websocket.WebSocketHandler):
    clients = dict()
    curr_id = 0
    queue = None
    def __init__(self, *args):
        super().__init__(*args)
        self.id = GameDataCollectHandler.curr_id
        self.queue = GameDataCollectHandler.queue

    def open(self, *args):
        self.id = GameDataCollectHandler.curr_id
        GameDataCollectHandler.clients[self.id] = self
        GameDataCollectHandler.curr_id += 1
        logging.info('GameDataCollect client connected')

    def on_message(self, message):
        #print(message)
        self.queue.put(message)
        for client_id in GameDataCollectHandler.clients:
            try:
                GameDataCollectHandler.clients[client_id].write_message(message)
            except Exception as e:
                GameDataCollectHandler.clients.pop(self.id, None)

    def on_close(self):
        GameDataCollectHandler.clients.pop(self.id, None)
        logging.info('GameDataCollect client disconnected')


def main():
    queue = mp.Queue() # process message queue
    p = TracertProcess(queue)
    p.start()
    GameDataCollectHandler.queue = queue

    parse_command_line()
    settings = dict(
            cookie_secret="SX4gEWPE6bVr0vbwGtMl",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            xsrf_cookies=True,
            debug=options.debug
    )

    handlers = [
        (r"/", MainHandler),
        (r"/gamedata-collect", GameDataCollectHandler),
        (r"/static/(.*)", tornado.web.StaticFileHandler, {"path": settings["static_path"]})
    ]

    app = tornado.web.Application(handlers, **settings)
    app.listen(options.port)
    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    main()
