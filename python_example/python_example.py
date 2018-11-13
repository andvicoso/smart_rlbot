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
        self.db = self.client['rl_game3']

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
        self.prev_controls.append(self.controller_state.__dict__)

        if self.previous_score < 0:
            self.previous_score = packet.game_cars[self.index].score_info.score

        # fucking detect the score
        current_score = packet.game_cars[self.index].score_info.score
        #print(self.index, self.previous_score, current_score)
        if self.previous_score != current_score and self.previous_score - current_score <= 125:
            event_data = []
            score_change = current_score - self.previous_score
            self.previous_score = current_score
            for i in range(len(self.prev_packets)):
                prev_packet = self.prev_packets[i]
                prev_control = self.prev_controls[i]
                event_data.append({
                    'who_got_score': self.index,
                    'score_change': score_change,
                    'seconds_elapsed_at_event': packet.game_info.seconds_elapsed,
                    'seconds_elapsed': prev_packet.game_info.seconds_elapsed,
                    'game_cars': [getdict(prev_packet.game_cars[i]) for i in range(6)],
                    'game_ball': getdict(prev_packet.game_ball),
                    'control_state': prev_control
                })


            self.db.custom_packets.insert(event_data)

            print('\n----------------------------------------------\nplayer {}\'s score changed by {} points\n----------------------------------------------\n'.format(self.index, score_change))
            
            self.prev_packets = []
            self.prev_controls = []

                 

    def think(self, packet):
        random_packets = self.db.custom_packets.aggregate([{ '$sample': { 'size': 40 } }])
        #random_packets = self.db.custom_packets.find({'seconds_elapsed':{'$gt': packet.game_info.seconds_elapsed-200}})

        if random_packets is None:
            self.default_action(packet)
        else:
            best_packet_data = None
            smallest_difference = 100000000000000
            for packet_data in random_packets:
                #pprint(packet_data)
                if random.uniform(0,1) > 0.5:
                    current_difference = packet_loss(packet, self.controller_state, self.index, packet_data)
                    if current_difference < smallest_difference:
                        smallest_difference = current_difference
                        best_packet_data = packet_data
            
            if best_packet_data is not None and random.uniform(0,1)>0.5: # take random with 5% possibility
                self.controller_state.throttle = best_packet_data['control_state']['throttle']
                self.controller_state.steer = best_packet_data['control_state']['steer']
                self.controller_state.pitch = best_packet_data['control_state']['pitch']
                self.controller_state.yaw = best_packet_data['control_state']['yaw']
                self.controller_state.roll = best_packet_data['control_state']['roll']
                self.controller_state.jump = best_packet_data['control_state']['jump']
                self.controller_state.boost = best_packet_data['control_state']['boost']
                self.controller_state.handbrake = best_packet_data['control_state']['handbrake']
                print("player {} copies action by player {} at {} (packet_loss={})".format(self.index, best_packet_data['who_got_score'], best_packet_data['seconds_elapsed'], smallest_difference))

            else:
                self.default_action(packet)
        
        


    def default_action(self, packet):
        """
        self.controller_state.throttle = random.uniform(-1, 1)
        self.controller_state.steer = random.uniform(-1, 1)
        self.controller_state.pitch = random.uniform(-1, 1)
        self.controller_state.yaw = random.uniform(-1, 1)
        self.controller_state.roll = random.uniform(-1, 1)
        self.controller_state.jump = random.getrandbits(1)
        self.controller_state.boost = random.getrandbits(1)
        self.controller_state.handbrake = random.getrandbits(1)
        """

        print("player {} takes default action".format(self.index))

        ball_location = Vector2(packet.game_ball.physics.location.x, packet.game_ball.physics.location.y)

        my_car = packet.game_cars[self.index]
        car_location = Vector2(my_car.physics.location.x, my_car.physics.location.y)
        car_direction = get_car_facing_vector(my_car)
        car_to_ball = ball_location - car_location

        steer_correction_radians = car_direction.correction_to(car_to_ball)

        if steer_correction_radians > 0:
            # Positive radians in the unit circle is a turn to the left.
            turn = -0.5  # Negative value for a turn to the left.
        else:
            turn = 0.5

        self.controller_state.pitch = random.uniform(-1, 1)
        self.controller_state.yaw = random.uniform(-1, 1)
        self.controller_state.roll = random.uniform(-1, 1)
        self.controller_state.jump = random.getrandbits(1)
        self.controller_state.boost = random.getrandbits(1)
        self.controller_state.handbrake = random.getrandbits(1)

        self.controller_state.throttle = 1.0
        self.controller_state.steer = turn

def packet_loss(curr_packet, control_state, i, prev_packet_data):
    res = 0
    #print(curr_packet_data['num_cars'], prev_packet_data['num_cars'])
    #for i in range(4):
    res += math.pow(curr_packet.game_cars[i].physics.location.x-prev_packet_data['game_cars'][prev_packet_data['who_got_score']]['physics']['location']['x'], 2)
    res += math.pow(curr_packet.game_cars[i].physics.location.y-prev_packet_data['game_cars'][prev_packet_data['who_got_score']]['physics']['location']['y'], 2)
    res += math.pow(curr_packet.game_cars[i].physics.location.z-prev_packet_data['game_cars'][prev_packet_data['who_got_score']]['physics']['location']['z'], 2)
    res += math.pow(curr_packet.game_cars[i].physics.rotation.pitch-prev_packet_data['game_cars'][prev_packet_data['who_got_score']]['physics']['rotation']['pitch'], 2)
    res += math.pow(curr_packet.game_cars[i].physics.rotation.yaw-prev_packet_data['game_cars'][prev_packet_data['who_got_score']]['physics']['rotation']['yaw'], 2)
    res += math.pow(curr_packet.game_cars[i].physics.rotation.roll-prev_packet_data['game_cars'][prev_packet_data['who_got_score']]['physics']['rotation']['roll'], 2)
    res += math.pow(curr_packet.game_cars[i].physics.velocity.x-prev_packet_data['game_cars'][prev_packet_data['who_got_score']]['physics']['velocity']['x'], 2)
    res += math.pow(curr_packet.game_cars[i].physics.velocity.y-prev_packet_data['game_cars'][prev_packet_data['who_got_score']]['physics']['velocity']['y'], 2)
    res += math.pow(curr_packet.game_cars[i].physics.velocity.z-prev_packet_data['game_cars'][prev_packet_data['who_got_score']]['physics']['velocity']['z'], 2)
    res += math.pow(curr_packet.game_cars[i].boost-prev_packet_data['game_cars'][i]['boost'], 2)


    res += math.pow(curr_packet.game_ball.physics.location.x-prev_packet_data['game_ball']['physics']['location']['x'], 2)
    res += math.pow(curr_packet.game_ball.physics.location.y-prev_packet_data['game_ball']['physics']['location']['y'], 2)
    res += math.pow(curr_packet.game_ball.physics.location.z-prev_packet_data['game_ball']['physics']['location']['z'], 2)
    res += math.pow(curr_packet.game_ball.physics.rotation.pitch-prev_packet_data['game_ball']['physics']['rotation']['pitch'], 2)
    res += math.pow(curr_packet.game_ball.physics.rotation.yaw-prev_packet_data['game_ball']['physics']['rotation']['yaw'], 2)
    res += math.pow(curr_packet.game_ball.physics.rotation.roll-prev_packet_data['game_ball']['physics']['rotation']['roll'], 2)
    res += math.pow(curr_packet.game_ball.physics.velocity.x-prev_packet_data['game_ball']['physics']['velocity']['x'], 2)
    res += math.pow(curr_packet.game_ball.physics.velocity.y-prev_packet_data['game_ball']['physics']['velocity']['y'], 2)
    res += math.pow(curr_packet.game_ball.physics.velocity.z-prev_packet_data['game_ball']['physics']['velocity']['z'], 2)
    res += 100*math.pow(curr_packet.game_ball.latest_touch.hit_location.x-prev_packet_data['game_ball']['latest_touch']['hit_location']['x'], 2)
    res += 100*math.pow(curr_packet.game_ball.latest_touch.hit_location.y-prev_packet_data['game_ball']['latest_touch']['hit_location']['y'], 2)
    res += 100*math.pow(curr_packet.game_ball.latest_touch.hit_location.z-prev_packet_data['game_ball']['latest_touch']['hit_location']['z'], 2)

    # controller state
    
    res += 1000*math.pow(control_state.throttle-prev_packet_data['control_state']['throttle'], 2)
    res += 1000*math.pow(control_state.steer-prev_packet_data['control_state']['steer'], 2)   
    res += 1000*math.pow(control_state.pitch-prev_packet_data['control_state']['pitch'], 2)   
    res += 1000*math.pow(control_state.yaw-prev_packet_data['control_state']['yaw'], 2)   
    res += 1000*math.pow(control_state.roll-prev_packet_data['control_state']['roll'], 2)   

    res += 100 if control_state.jump != prev_packet_data['control_state']['jump'] else 0
    res += 100 if control_state.boost != prev_packet_data['control_state']['boost'] else 0
    res += 100 if control_state.handbrake != prev_packet_data['control_state']['handbrake'] else 0
   
    
    return math.sqrt(res)/prev_packet_data['score_change']


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


class Vector2:
    def __init__(self, x=0, y=0):
        self.x = float(x)
        self.y = float(y)

    def __add__(self, val):
        return Vector2(self.x + val.x, self.y + val.y)

    def __sub__(self, val):
        return Vector2(self.x - val.x, self.y - val.y)

    def correction_to(self, ideal):
        # The in-game axes are left handed, so use -x
        current_in_radians = math.atan2(self.y, -self.x)
        ideal_in_radians = math.atan2(ideal.y, -ideal.x)

        correction = ideal_in_radians - current_in_radians

        # Make sure we go the 'short way'
        if abs(correction) > math.pi:
            if correction < 0:
                correction += 2 * math.pi
            else:
                correction -= 2 * math.pi

        return correction


def get_car_facing_vector(car):
    pitch = float(car.physics.rotation.pitch)
    yaw = float(car.physics.rotation.yaw)

    facing_x = math.cos(pitch) * math.cos(yaw)
    facing_y = math.cos(pitch) * math.sin(yaw)

    return Vector2(facing_x, facing_y)
