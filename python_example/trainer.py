import multiprocessing as mp

from keras.models import Sequential
from keras.layers import Dense
from keras.models import model_from_json
import numpy
import os

class TrainProcess(mp.Process):
    def __init__(self, packet, who):
        mp.Process.__init__(self)
        self.packet = packet
        self.who = who

    def run(self):
        """
        try:
            json_file = open('model.json', 'r')
            model_json = json_file.read()
            json_file.close()
            model = model_from_json(model_json)
            # load weights into new model
            model.load_weights("model.h5")
            print("Loaded model from disk")
        except Exception as e:
            return

        # evaluate loaded model on test data
        model.compile(loss='binary_crossentropy', optimizer='rmsprop', metrics=['accuracy'])
        score = model.evaluate(X, Y, verbose=0)
        print("%s: %.2f%%" % (model.metrics_names[1], score[1]*100))
        """