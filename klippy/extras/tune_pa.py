# Helper script for tuning pressure advance
#
# Copyright (C) 2019  Kevin O'Connor <kevin@koconnor.net>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import logging

class TunePressureAdvance:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.tune = self.printer.try_load_module(config, "tuning_tower")
        # Register command
        self.gcode = gcode = self.printer.lookup_object("gcode")
        gcode.register_command("TUNE_PRESSURE_ADVANCE",
                               self.cmd_TUNE_PRESSURE_ADVANCE,
                               desc=self.cmd_TUNE_PRESSURE_ADVANCE_help)
        gcode.register_command(
            "TUNE_PRESSURE_ADVANCE_SMOOTH_TIME",
            self.cmd_TUNE_PRESSURE_ADVANCE_SMOOTH_TIME,
            desc=self.cmd_TUNE_PRESSURE_ADVANCE_SMOOTH_TIME_help)
    cmd_TUNE_PRESSURE_ADVANCE_help = "Tune extruder pressure advance"
    def cmd_TUNE_PRESSURE_ADVANCE(self, params):
        self.tune.start_tuning_test(params, self.update_pa)
        self.gcode.run_script_from_command(
            "SET_VELOCITY_LIMIT ACCEL=500 SQUARE_CORNER_VELOCITY=1")
    def update_pa(self, z, val):
        logging.info("TUNE_PRESSURE_ADVANCE z=%.3f pa=%.6f", z, val)
        self.gcode.run_script_from_command(
            "SET_PRESSURE_ADVANCE ADVANCE=%.6f" % (val,))
    cmd_TUNE_PRESSURE_ADVANCE_SMOOTH_TIME_help = "Tune pressure smooth time"
    def cmd_TUNE_PRESSURE_ADVANCE_SMOOTH_TIME(self, params):
        self.tune.start_tuning_test(params, self.update_smooth)
        self.gcode.run_script_from_command(
            "SET_VELOCITY_LIMIT ACCEL=500 SQUARE_CORNER_VELOCITY=1")
    def update_smooth(self, z, val):
        logging.info("TUNE_PRESSURE_ADVANCE_SMOOTH_TIME z=%.3f t=%.6f", z, val)
        self.gcode.run_script_from_command(
            "SET_PRESSURE_ADVANCE SMOOTH_TIME=%.6f" % (val,))

def load_config(config):
    return TunePressureAdvance(config)
