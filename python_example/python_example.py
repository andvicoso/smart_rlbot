import math
import json
import asyncio
from pymongo import MongoClient

from rlbot.agents.base_agent import BaseAgent, SimpleControllerState
from rlbot.utils.structures.game_data_struct import GameTickPacket

from pprint import pprint

import multiprocessing as mp

import random

class PythonExample(BaseAgent):

    def initialize_agent(self):
        #This runs once before the bot starts up
        self.controller_state = SimpleControllerState()

        self.client = MongoClient('10.140.11.149', 36281)
        self.db = self.client['rl_game']

        self.previous_score = -1
        self.previous_event_time = 0

        self.tick_count = 0

        self.prev_packets = []
        self.prev_controls = []

    def get_output(self, packet: GameTickPacket) -> SimpleControllerState:
        #self.renderer.begin_rendering()
        #self.renderer.draw_rect_2d(20, 20, 200, 200, True, self.renderer.black())
        #self.renderer.end_rendering()

        """ action by model """
        if self.tick_count == 60:
            self.tick_count = 0
            #p = TrainProcess(packet, self.index)
            #p.start()
            self.think(packet)
            
            self.store_data(packet)
        else:
            self.tick_count += 1

        return self.controller_state

    def store_data(self, packet):
        """
        packet_data = {
            'who': self.index,
            'game_cars': [getdict(packet.game_cars[i]) for i in range(packet.num_cars)],
            'num_cars': packet.num_cars,
            'game_boosts': [getdict(packet.game_boosts[i]) for i in range(packet.num_cars)],
            'num_boost': packet.num_boost,
            'game_ball': getdict(packet.game_ball),
            'game_info': getdict(packet.game_info),
            'controller_state': self.controller_state.__dict__
        }
        self.db.packets.insert_one(packet_data)
        """

        self.prev_packets.append(packet)
        self.prev_controls.append(self.controller_state)

        if self.previous_score < 0:
            self.previous_score = packet.game_cars[self.index].score_info.score

        # fucking detect the score
        current_score = packet.game_cars[self.index].score_info.score
        if self.previous_score != current_score:
            event_data = {
                'who': self.index,
                'score_change': current_score - self.previous_score,
                'seconds_elapsed': packet.game_info.seconds_elapsed,
                'cars': [],
                'ball': [],
                'control': self.prev_controls
            }
            for prev_packet in self.prev_packets:
                event_data['cars'].append(prev_packet.game_cars)
                event_data['ball'].append(prev_packet.game_ball)

            pprint(event_data)
            
            self.db.events.insert_one(event_data)
            self.previous_scores = current_score     

    def think(self, packet):
        self.controller_state.throttle = random.uniform(-1, 1)
        self.controller_state.steer = random.uniform(-1, 1)
        self.controller_state.pitch = random.uniform(-1, 1)
        self.controller_state.yaw = random.uniform(-1, 1)
        self.controller_state.roll = random.uniform(-1, 1)
        self.controller_state.jump = random.getrandbits(1)
        self.controller_state.boost = random.getrandbits(1)
        self.controller_state.handbrake = random.getrandbits(1)

def packet_difference(curr_packet_data, prev_packet_data):
    res = 0
    #print(curr_packet_data['num_cars'], prev_packet_data['num_cars'])
    for i in range(curr_packet_data['num_cars']):
        res += math.pow(curr_packet_data['game_cars'][i]['physics']['location']['x']-prev_packet_data['game_cars'][i]['physics']['location']['x'], 2)
    return math.sqrt(res)


def getdict(struct):
    result = {}
    for field, _ in struct._fields_:
         value = getattr(struct, field)
         # if the type is not a primitive and it evaluates to False ...
         if (type(value) not in [int, float, bool]) and not bool(value):
             # it's a null pointer
             value = None
         elif hasattr(value, "_length_") and hasattr(value, "_type_"):
             # Probably an array
             value = list(value)
         elif hasattr(value, "_fields_"):
             # Probably another struct
             value = getdict(value)
         result[field] = value
    return result
