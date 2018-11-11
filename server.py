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

from pymongo import MongoClient

CHECK_INTERVAL = 1

define("port", default=8080, help="run on the given port", type=int)
define("debug", default=True, help="run in debug mode")
#define("autoreload", default=True, help="run in debug mode")

lock = tornado.locks.Lock()


class TracertProcess(mp.Process):
    def __init__(self, queue, queue2):
        """
        Asynchronously parse tracert

        :param target: target address/name
        :param on_new_node: function to execute when new node is detected
        :return: return code (-1 = timeout, 0 = ok, 1 = command error, 2 = force terminated)
        """
        mp.Process.__init__(self)
        self.queue = queue
        self.queue2 = queue2

        
        #print(self.client)
        #self.db = self.client['gamedata']

    def run(self):
        self.client = MongoClient()
        self.db = self.client['gamedata']
        self.gamedata = self.db['gamedata']
        self.goaldata = self.db['goaldata']
        while True:
            while not self.queue.empty():
                data = self.queue.get_nowait()
                self.gamedata.insert_one(data)
            while not self.queue2.empty():
                data = self.queue2.get_nowait()
                self.goaldata.insert_one(data)


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("index.html")


class GameDataCollectHandler(tornado.websocket.WebSocketHandler):
    clients = dict()
    curr_id = 0
    queue = None
    queue2 = None
    def __init__(self, *args):
        super().__init__(*args)
        self.id = GameDataCollectHandler.curr_id
        self.queue = GameDataCollectHandler.queue
        self.queue2 = GameDataCollectHandler.queue2

        self.previousGoals = [0,0,0,0,0,0,0,0,0,0]
        self.previousOwnGoals = [0,0,0,0,0,0,0,0,0,0]
        self.previousdata_init = False

    def open(self, *args):
        self.id = GameDataCollectHandler.curr_id
        GameDataCollectHandler.clients[self.id] = self
        GameDataCollectHandler.curr_id += 1
        logging.info('GameDataCollect client connected')

    def on_message(self, message):
        #print(message)
        data = json.loads(message)
        self.queue.put(data)

        if not self.previousdata_init:
            self.previousdata_init = True
            for i in range(data['num_cars']):
                self.previousGoals[i] = data['game_cars'][i]['score_info']['goals']
                self.previousOwnGoals[i] = data['game_cars'][i]['score_info']['own_goals']

        
        # fucking detect the goal
        for i in range(data['num_cars']):
            if self.previousGoals[i] != data['game_cars'][i]['score_info']['goals']:
                self.previousGoals[i] = data['game_cars'][i]['score_info']['goals']
                goaldata = {
                    'by': i,
                    'seconds_elapsed': data['game_info']['seconds_elapsed'],
                    'own_goal_by': -1
                }
                
                # check for own goals
                for j in range(data['num_cars']):
                    if self.previousOwnGoals[j] != data['game_cars'][j]['score_info']['own_goals']:
                        self.previousOwnGoals[j] = data['game_cars'][j]['score_info']['own_goals']
                        goaldata['own_goal_by'] = j
                        break

                self.queue2.put(goaldata)
                break
        
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
    queue2 = mp.Queue() # process message queue
    p = TracertProcess(queue, queue2)
    p.start()
    GameDataCollectHandler.queue = queue
    GameDataCollectHandler.queue2 = queue2

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
