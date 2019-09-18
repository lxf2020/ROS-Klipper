// Extruder stepper pulse time generation
//
// Copyright (C) 2018  Kevin O'Connor <kevin@koconnor.net>
//
// This file may be distributed under the terms of the GNU GPLv3 license.

#include <stddef.h> // offsetof
#include <stdlib.h> // malloc
#include <string.h> // memset
#include "compiler.h" // __visible
#include "itersolve.h" // struct stepper_kinematics
#include "stepcompress.h" // XXX - extruder_flush
#include "pyhelper.h" // errorf

static double
extruder_calc_position(struct stepper_kinematics *sk, struct move *m
                       , double move_time)
{
    return m->start_pos.x + move_get_distance(m, move_time);
}

struct stepper_kinematics * __visible
extruder_stepper_alloc(void)
{
    struct stepper_kinematics *sk = malloc(sizeof(*sk));
    memset(sk, 0, sizeof(*sk));
    list_init(&sk->moves);
    sk->calc_position = extruder_calc_position;
    return sk;
}

// xxx - Need an extruder_stepper_free() function

// Populate a 'struct move' with an extruder velocity trapezoid
void __visible
extruder_move_fill(struct stepper_kinematics *sk, double print_time
                   , double accel_t, double cruise_t, double decel_t
                   , double start_pos
                   , double start_v, double cruise_v, double accel
                   , double extra_accel_v, double extra_decel_v)
{
    struct move *m = move_alloc();

    // Setup velocity trapezoid
    m->print_time = print_time;
    m->move_t = accel_t + cruise_t + decel_t;
    m->accel_t = accel_t;
    m->cruise_t = cruise_t;
    m->cruise_start_d = accel_t * (.5 * (cruise_v + start_v) + extra_accel_v);
    m->decel_start_d = m->cruise_start_d + cruise_t * cruise_v;

    // Setup for accel/cruise/decel phases
    m->cruise_v = cruise_v;
    m->accel.c1 = start_v + extra_accel_v;
    m->accel.c2 = .5 * accel;
    m->decel.c1 = cruise_v + extra_decel_v;
    m->decel.c2 = -m->accel.c2;

    // Setup start distance
    m->start_pos.x = start_pos;

    // Add to list
    list_add_tail(&m->node, &sk->moves);
}

// XXX
int
extruder_flush(struct stepper_kinematics *sk
               , double step_gen_time, double print_time)
{
    struct move *m, *next;
    list_for_each_entry_safe(m, next, &sk->moves, node) {
        int32_t ret = itersolve_gen_steps(sk, m);
        if (ret)
            // XXX - free list
            return ret;
        list_del(&m->node);
        free(m);
    }
    return 0;
}
