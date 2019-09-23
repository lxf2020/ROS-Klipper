This document provides information on tuning the "pressure advance"
configuration variable for a particular nozzle and filament. The
pressure advance feature can be helpful in reducing ooze. For more
information on how pressure advance is implemented see the
[kinematics](Kinematics.md) document.

Tuning pressure advance
=======================

Pressure advance does two useful things - it reduces ooze during
non-extrude moves and it reduces blobbing during cornering. This guide
uses the second feature (reducing blobbing during cornering) as a
mechanism for tuning.

In order to calibrate pressure advance the printer must be configured
and operational as the tuning test involves printing and inspecting a
test object. It is a good idea to read this document in full prior to
running the test.

Use a slicer to generate g-code for the large hollow square found in
[docs/prints/square_tower.stl](prints/square_tower.stl). Use a high
speed (eg, 100mm/s), zero infill, and a coarse layer height (the layer
height should be around 75% of the nozzle diameter).

For printers with a direct drive extruder run the command
`TUNE_PRESSURE_ADVANCE START=0.000 INCREMENT=.005`. For long bowden
extruders use `TUNE_PRESSURE_ADVANCE START=0.000 INCREMENT=.020`. Then
print the object. When fully printed the test print looks like:

![tuning_tower](img/tuning_tower.jpg)

The TUNE_PRESSURE_ADVANCE command instructs Klipper to alter the
pressure_advance setting on each layer of the print. Higher layers in
the print will have a larger pressure advance value set. Layers below
the ideal pressure_advance setting will have blobbing at the corners,
and layers above the ideal setting can lead to rounded corners and
poor extrusion leading up to the corner.

One can cancel the print early if one observes that the corners are no
longer printing well (and thus one can avoid printing layers that are
known to be above the ideal pressure_advance value).

Inspect the print and then use a digital calipers to find the height
that has the best quality corners. When in doubt, prefer a lower
height.

![tune_pa](img/tune_pa.jpg)

The pressure_advance value can then be calculated as `pressure_advance
= <start> + <measured_height> * <increment>`. (For example,
`0.000 + 12.90 * .020` would be `.258`.)

It is possible to choose custom settings for START and INCREMENT if
that helps identify the best pressure advance setting. When doing
this, be sure to issue the TUNE_PRESSURE_ADVANCE command at the start
of each test print.

Typical pressure advance values are between 0.050 and 1.000 (the high
end usually only with bowden extruders). If there is no significant
improvement with a pressure advance up to 1.000, then pressure advance
is unlikely to improve the quality of prints. Return to a default
configuration with pressure advance disabled.

Although this tuning exercise directly improves the quality of
corners, it's worth remembering that a good pressure advance
configuration also reduces ooze throughout the print.

At the completion of this test, update the extruder's pressure_advance
setting in the configuration file and issue a RESTART command. The
RESTART command will clear the test state and return the acceleration
and cornering speeds to their normal values.

Important Notes
===============

* The pressure advance value is dependent on the extruder, the nozzle,
  and the filament. It is common for filament from different
  manufactures or with different pigments to require significantly
  different pressure advance values. Therefore, one should calibrate
  pressure advance on each printer and with each spool of filament.

* Printing temperature and extrusion rates can impact pressure
  advance.  Be sure to tune the extruder
  [E steps](http://reprap.org/wiki/Triffid_Hunter%27s_Calibration_Guide#E_steps)
  and
  [nozzle temperature](http://reprap.org/wiki/Triffid_Hunter%27s_Calibration_Guide#Nozzle_Temperature)
  prior to tuning pressure advance.

* It is not unusual for one corner of the test print to be
  consistently different than the other three corners. This typically
  occurs when the slicer arranges to always change Z height at that
  corner. If this occurs, then ignore that corner and tune pressure
  advance using the other three corners.

* If a high pressure advance value (eg, over 0.200) is used then one
  may find that the extruder skips when returning to the printer's
  normal acceleration. The pressure advance system accounts for
  pressure by pushing in extra filament during acceleration and
  retracting that filament during deceleration. With a high
  acceleration and high pressure advance the extruder may not have
  enough torque to push the required filament. If this occurs, either
  use a lower acceleration value or disable pressure advance.

* Once pressure advance is tuned in Klipper, it may still be useful to
  configure a small retract value in the slicer (eg, 0.75mm) and to
  utilize the slicer's "wipe on retract option" if available. These
  slicer settings may help counteract ooze caused by filament cohesion
  (filament pulled out of the nozzle due to the stickiness of the
  plastic). It is recommended to disable the slicer's "z-lift on
  retract" option.

* Configuring pressure advance results in extra extruder movement
  during move acceleration and deceleration. That extra movement is
  not further constrained by any other other configuration parameter.
  The pressure advance settings only impact extruder movement; they do
  not alter toolhead XYZ movement or look-ahead calculations. A change
  in pressure advance will not change the path or timing of the
  toolhead nor will it change the overall printing time.
