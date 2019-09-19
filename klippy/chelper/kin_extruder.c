// Extruder stepper pulse time generation
//
// Copyright (C) 2018-2019  Kevin O'Connor <kevin@koconnor.net>
//
// This file may be distributed under the terms of the GNU GPLv3 license.

#include <stddef.h> // offsetof
#include <stdlib.h> // malloc
#include <string.h> // memset
#include "compiler.h" // __visible
#include "itersolve.h" // struct stepper_kinematics
#include "stepcompress.h" // XXX - extruder_flush
#include "pyhelper.h" // errorf

struct extruder_stepper {
    struct stepper_kinematics sk;
    double cur_move_time;
    double pressure_advance, smooth_time;
};

static double
extruder_calc_position(struct stepper_kinematics *sk, struct move *m
                       , double move_time)
{
    return m->start_pos.x + move_get_distance(m, move_time);
}

struct stepper_kinematics * __visible
extruder_stepper_alloc(void)
{
    struct extruder_stepper *es = malloc(sizeof(*es));
    memset(es, 0, sizeof(*es));
    list_init(&es->sk.moves);
    es->sk.calc_position = extruder_calc_position;
    return &es->sk;
}

// xxx - Need an extruder_stepper_free() function

// Populate a 'struct move' with an extruder velocity trapezoid
void __visible
extruder_move_fill(struct stepper_kinematics *sk, double print_time
                   , double accel_t, double cruise_t, double decel_t
                   , double start_pos, double start_pa_pos
                   , double start_v, double cruise_v, double accel
                   , int is_pa_move)
{
    struct move *m = move_alloc();

    // Setup velocity trapezoid
    m->print_time = print_time;
    m->move_t = accel_t + cruise_t + decel_t;
    m->accel_t = accel_t;
    m->cruise_t = cruise_t;
    m->cruise_start_d = accel_t * .5 * (cruise_v + start_v);
    m->decel_start_d = m->cruise_start_d + cruise_t * cruise_v;

    // Setup for accel/cruise/decel phases
    m->cruise_v = cruise_v;
    m->accel.c1 = start_v;
    m->accel.c2 = .5 * accel;
    m->decel.c1 = cruise_v;
    m->decel.c2 = -m->accel.c2;

    // Setup start distance
    m->start_pos.x = start_pos;

    // Add to list
    list_add_tail(&m->node, &sk->moves);
}

void __visible
extruder_set_pressure(struct stepper_kinematics *sk
                      , double pressure_advance, double smooth_time)
{
    struct extruder_stepper *es = container_of(sk, struct extruder_stepper, sk);
    es->pressure_advance = pressure_advance;
    es->smooth_time = smooth_time;
}

// XXX
int
extruder_flush(struct stepper_kinematics *sk
               , double step_gen_time, double print_time)
{
    struct extruder_stepper *es = container_of(sk, struct extruder_stepper, sk);
    double flush_time = print_time - es->smooth_time;
    if (flush_time < step_gen_time)
        flush_time = step_gen_time;

    while (!list_empty(&es->sk.moves)) {
        struct move *m = list_first_entry(&es->sk.moves, struct move, node);
        double move_print_time = m->print_time;
        if (move_print_time >= flush_time)
            break;
        double start = es->cur_move_time, end = m->move_t;
        if (move_print_time + end > flush_time)
            end = flush_time - move_print_time;
        int32_t ret = itersolve_gen_steps_range(sk, m, start, end);
        if (ret)
            return ret;
        if (end < m->move_t) {
            es->cur_move_time = end;
            break;
        }
        es->cur_move_time = 0.;
        list_del(&m->node);
        free(m);
    }
    return 0;
}
