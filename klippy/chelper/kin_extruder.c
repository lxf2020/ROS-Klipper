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
    double last_print_time;
    double pressure_advance_factor, smooth_time;
};

static double
extruder_calc_position(struct stepper_kinematics *sk, struct move *m
                       , double move_time)
{
    struct extruder_stepper *es = container_of(sk, struct extruder_stepper, sk);
    double dist = move_get_distance(m, move_time);
    double base_pos = m->start_pos.x + dist;
    if (! es->smooth_time)
        return base_pos;
    double pa_start_pos = m->start_pos.y + (m->start_pos.z ? dist : 0.);
    double end_time = move_time + es->smooth_time;
    for (;;) {
        if (end_time <= m->move_t)
            break;
        if (m->node.next == &es->sk.moves.root) {
            end_time = m->move_t;
            break;
        }
        struct move *next_move = container_of(m->node.next, struct move, node);
        if (end_time <= next_move->print_time - m->print_time) {
            end_time = m->move_t;
            break;
        }
        end_time -= next_move->print_time - m->print_time;
        m = next_move;
    }
    double end_dist = move_get_distance(m, end_time);
    double pa_end_pos = m->start_pos.y + (m->start_pos.z ? end_dist : 0.);
    return base_pos + (pa_end_pos - pa_start_pos) * es->pressure_advance_factor;
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
    m->start_pos.y = start_pa_pos;
    m->start_pos.z = is_pa_move; // XXX

    // Add to list
    list_add_tail(&m->node, &sk->moves);
}

void __visible
extruder_set_pressure(struct stepper_kinematics *sk
                      , double pressure_advance, double smooth_time)
{
    struct extruder_stepper *es = container_of(sk, struct extruder_stepper, sk);
    if (! smooth_time) {
        es->pressure_advance_factor = es->smooth_time = 0.;
        return;
    }
    es->pressure_advance_factor = pressure_advance / smooth_time;
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

    struct move null_move;
    while (!list_empty(&es->sk.moves)) {
        struct move *m = list_first_entry(&es->sk.moves, struct move, node);
        double move_print_time = m->print_time;
        double last_print_time = es->last_print_time;
        if (last_print_time >= move_print_time + m->move_t) {
            list_del(&m->node);
            free(m);
            continue;
        }
        if (es->smooth_time && last_print_time + .000000001 < move_print_time) {
            // Insert null move
            double null_print_time = move_print_time - es->smooth_time;
            if (last_print_time > null_print_time)
                null_print_time = last_print_time;
            memset(&null_move, 0, sizeof(null_move));
            null_move.node.next = &m->node;
            null_move.print_time = null_print_time;
            null_move.move_t = move_print_time - null_print_time;
            null_move.cruise_t = null_move.move_t;
            null_move.start_pos = m->start_pos;
            m = &null_move;
            move_print_time = null_print_time;
        }

        double start = 0., end = m->move_t;
        if (last_print_time > move_print_time)
            start = last_print_time - move_print_time;
        if (move_print_time + start >= flush_time)
            break;
        if (move_print_time + end > flush_time)
            end = flush_time - move_print_time;
        int32_t ret = itersolve_gen_steps_range(sk, m, start, end);
        if (ret)
            return ret;
        es->last_print_time = move_print_time + end;
    }
    return 0;
}
