import math
import json
import asyncio
import numpy as np
import random
from pprint import pprint

from rlbot.agents.base_agent import BaseAgent, SimpleControllerState
from rlbot.utils.structures.game_data_struct import GameTickPacket


class PythonExample(BaseAgent):

    def initialize_agent(self):
        #This runs once before the bot starts up
        self.controller_state = SimpleControllerState()

        self.tick_count = 0

        self.prev_packets = []
        self.prev_controls = []

    def get_output(self, packet: GameTickPacket) -> SimpleControllerState:
        #self.renderer.begin_rendering()
        #self.renderer.draw_rect_2d(20, 20, 200, 200, True, self.renderer.black())
        #self.renderer.end_rendering()

        """ action by model """
        if self.tick_count == 10:
            self.tick_count = 0
            #p = TrainProcess(packet, self.index)
            #p.start()
            self.think(packet)
            
            #self.store_data(packet)
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

        self.prev_packets.append(packet)
        self.prev_controls.append(self.controller_state.__dict__)

                 

    def think(self, packet):
        self.default_action(packet)
        

    def default_action(self, packet):
        """
        # completely random
        self.controller_state.throttle = random.randint(-1, 1)
        self.controller_state.steer = random.randint(-1, 1)
        self.controller_state.pitch = random.randint(-1, 1)
        self.controller_state.yaw = random.randint(-1, 1)
        self.controller_state.roll = random.randint(-1, 1)
        self.controller_state.jump = random.getrandbits(1)
        self.controller_state.boost = random.getrandbits(1)
        self.controller_state.handbrake = random.getrandbits(1)
        """

        car = packet.game_cars[self.index]

        #if self.index == 1:
        #    print(car.physics.rotation.pitch)

        car_location = np.array((car.physics.location.x, car.physics.location.y))
        ball_location = np.array((packet.game_ball.physics.location.x, packet.game_ball.physics.location.y))
        car_to_ball_distance = np.subtract(ball_location, car_location)
        car_to_ball_angle = np.arctan(car_to_ball_distance[1]/car_to_ball_distance[0])
        if car_to_ball_distance[0] < 0:
            if car_to_ball_distance[1] > 0:
                car_to_ball_angle = np.pi + car_to_ball_angle
            else:
                car_to_ball_angle = -1*(np.pi - car_to_ball_angle)

        # make it normal poler coordinate
        car_angle = car.physics.rotation.yaw

        angle_difference = np.subtract(car_to_ball_angle, car_angle)

        if np.absolute(angle_difference) > np.pi:
            if angle_difference < 0:
                angle_difference += 2 * np.pi
            else:
                angle_difference -= 2 * np.pi

        if self.index == 0:
            print('car location ', car_location)
            print('ball location', ball_location)
            print('car to ball distance', car_to_ball_distance)
            print('car to ball angle', car_to_ball_angle )
            print('car angle', car_angle )
            print('angle difference', angle_difference )
            print()
            #print(car.physics.rotation.yaw, ideal_yaw, difference)


        self.controller_state.throttle = 1
        self.controller_state.steer = 1 if angle_difference > 0 else -1

        return self.controller_state

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


