import math
import json
import asyncio
from pymongo import MongoClient

from rlbot.agents.base_agent import BaseAgent, SimpleControllerState
from rlbot.utils.structures.game_data_struct import GameTickPacket

from pprint import pprint


class PythonExample(BaseAgent):

    controller_states = {}

    def initialize_agent(self):
        #This runs once before the bot starts up
        self.controller_state = SimpleControllerState()

        self.client = MongoClient('10.140.11.149', 36281)
        self.db = self.client['rl_game']

        self.previous_scores = [0,0,0,0,0,0,0,0,0,0]
        self.previous_scores_init = False

        self.tick_count = 0

    def get_output(self, packet: GameTickPacket) -> SimpleControllerState:

        packet_data = {
            'game_cars': [getdict(packet.game_cars[i]) for i in range(packet.num_cars)],
            'num_cars': packet.num_cars,
            'game_boosts': [getdict(packet.game_boosts[i]) for i in range(packet.num_cars)],
            'num_boost': packet.num_boost,
            'game_ball': getdict(packet.game_ball),
            'game_info': getdict(packet.game_info)
        }

        if len(PythonExample.controller_states) == packet.num_cars:
            controller_state_data = {}
            controller_state_data['seconds_elapsed'] = packet.game_info.seconds_elapsed
            controller_state_data['states'] = PythonExample.controller_states
            self.db.controller_states.insert_one(controller_state_data)
            PythonExample.controller_states = {}
        else:
            PythonExample.controller_states[self.index] = self.controller_state.__dict__


        self.store_data(packet_data)

        if not self.previous_scores_init:
            self.previous_scores_init = True
            for i in range(packet_data['num_cars']):
                self.previous_scores[i] = packet_data['game_cars'][i]['score_info']['score']

        """ action by model """
        if self.tick_count == 60:
            self.tick_count = 0

            self.think(packet, packet_data)
        else:
            self.tick_count += 1


        return self.controller_state

    def store_data(self, packet_data):
        #print(data)
        self.db.packets.insert_one(packet_data)

        # fucking detect the screoaejoreawjora  
        current_score = packet_data['game_cars'][self.index]['score_info']['score']
        if self.previous_scores[self.index] != current_score:
            event_data = {
                'who': self.index,
                'score_change': current_score - self.previous_scores[self.index],
                'seconds_elapsed': packet_data['game_info']['seconds_elapsed']
            }
            pprint(event_data)
            
            self.db.events.insert_one(event_data)
            self.previous_scores[self.index] = current_score   

    def make_default_action(self, packet):
        ball_location = Vector2(packet.game_ball.physics.location.x, packet.game_ball.physics.location.y)

        my_car = packet.game_cars[self.index]
        car_location = Vector2(my_car.physics.location.x, my_car.physics.location.y)
        car_direction = get_car_facing_vector(my_car)
        car_to_ball = ball_location - car_location

        steer_correction_radians = car_direction.correction_to(car_to_ball)

        if steer_correction_radians > 0:
            # Positive radians in the unit circle is a turn to the left.
            turn = -1.0  # Negative value for a turn to the left.
        else:
            turn = 1.0

        self.controller_state.throttle = 1.0
        self.controller_state.steer = turn     

    def think(self, packet, packet_data):
        #self.make_default_action(packet)
        # pick 10 random points
        prev_data_cursor = self.db.packets.aggregate([{ '$sample': { 'size': 20 } }])
        most_similar_prev_data = None
        min_packet_difference = 1000000000000000
        for prev_data in prev_data_cursor:
            if most_similar_prev_data is None:
                most_similar_prev_data = prev_data
            current = packet_difference(packet_data, prev_data)
            if current < min_packet_difference:
                min_packet_difference = current
                most_similar_prev_data = prev_data

        #pprint(most_similar_prev_data['game_info']['seconds_elapsed'])

        

        most_similar_state_data = self.db.controller_states.find_one({
            'seconds_elapsed': {'$gt': most_similar_prev_data['game_info']['seconds_elapsed']-2, '$lt': most_similar_prev_data['game_info']['seconds_elapsed']}
        })
        if most_similar_state_data is not None:
            who = 0
            pprint(most_similar_state_data)
            print("{} controller state updated based on {}".format(self.index, who))
            self.controller_state.throttle = most_similar_state_data['states'][who]['throttle']
            self.controller_state.steer = most_similar_state_data['states'][who]['steer']
            self.controller_state.pitch = most_similar_state_data['states'][who]['pitch']
            self.controller_state.yaw = most_similar_state_data['states'][who]['yaw']
            self.controller_state.roll = most_similar_state_data['states'][who]['roll']
            self.controller_state.jump = most_similar_state_data['states'][who]['jump']
            self.controller_state.boost = most_similar_state_data['states'][who]['boost']
            self.controller_state.handbrake = most_similar_state_data['states'][who]['handbrake']

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


def make_default_action(controller_state, packet, who):
    ball_location = Vector2(packet.game_ball.physics.location.x, packet.game_ball.physics.location.y)

    my_car = packet.game_cars[who]
    car_location = Vector2(my_car.physics.location.x, my_car.physics.location.y)
    car_direction = get_car_facing_vector(my_car)
    car_to_ball = ball_location - car_location

    steer_correction_radians = car_direction.correction_to(car_to_ball)

    if steer_correction_radians > 0:
        # Positive radians in the unit circle is a turn to the left.
        turn = -1.0  # Negative value for a turn to the left.
    else:
        turn = 1.0

    controller_state.throttle = 1.0
    controller_state.steer = turn


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
