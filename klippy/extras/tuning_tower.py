# Helper script for tuning via a tuning tower print
#
# Copyright (C) 2019  Kevin O'Connor <kevin@koconnor.net>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import logging

class TuningTower:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.normal_transform = None
        self.last_position = [0., 0., 0., 0.]
        self.last_z = self.start = self.increment = 0.
        self.callback = None
    def start_tuning_test(self, params, callback):
        if self.normal_transform is not None:
            self.end_test()
        # Get parameters
        gcode = self.printer.lookup_object("gcode")
        start = gcode.get_float('START', params, 0.)
        increment = gcode.get_float('INCREMENT', params)
        logging.info("Starting tuning test (start=%.6f increment=%.6f)",
                     start, increment)
        # Enable test mode
        self.callback = callback
        self.normal_transform = gcode.set_move_transform(self, force=True)
        self.last_z = 0.
        self.start = start
        self.increment = increment
        gcode.reset_last_position()
        self.get_position()
    def get_position(self):
        pos = self.normal_transform.get_position()
        self.last_postition = list(pos)
        return pos
    def move(self, newpos, speed):
        normal_transform = self.normal_transform
        if (newpos[3] > self.last_position[3] and newpos[2] != self.last_z
            and newpos[:3] != self.last_position[:3]):
            # Extrusion move at new z height
            z = newpos[2]
            if z > self.last_z:
                # Process update
                self.last_z = z
                self.callback(z, self.start + z * self.increment)
            else:
                self.end_test()
        # Forward move to actual handler
        self.last_position[:] = newpos
        normal_transform.move(newpos, speed)
    def end_test(self):
        gcode = self.printer.lookup_object("gcode")
        gcode.respond_info("Ending tuning test mode")
        gcode.set_move_transform(self.normal_transform, force=True)
        self.normal_transform = None

def load_config(config):
    return TuningTower(config)
