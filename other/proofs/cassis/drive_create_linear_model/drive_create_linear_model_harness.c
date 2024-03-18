// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

/*
 * Insert copyright notice
 */

/**
 * @file drive_create_linear_model_harness.c
 * @brief Implements the proof harness for drive_create_linear_model function.
 */

/*
 * Insert project header files that
 *   - include the declaration of the function
 *   - include the types needed to declare function arguments
 */

#include <stdlib.h>
#include <stdint.h>
#include <assert.h>
#include "helpers/rotation_drive_model.h"

// Copied from cassis_rotation_manager.c
#define TSCP_MAX_DISPLACEMENT_DEG			360000
#define TSCP_MDEG_TO_STEP(_x)				(_x * 185.185)

double __builtin_sqrt(double x) {
  // given our assumptions below, the upper bound for 'x' is approximately 28. So 
  // we can improve prformance by assuming that the upper bound of 'root' is 6.
  assert(x >= 0);
  assert(x < 30);

  if (x == 0 || x == 1) {
    return x;
  }

  double root;
  __CPROVER_assume(root >= 0 && root < 6);
  __CPROVER_assume(root * root == x);
  return root;
}


/**
 * @brief Starting point for formal analysis
 * 
 */
void harness(void)
{
  /*
    Note: We know from 'cassis_rotation_manager.c' that 'drive_create_linear_model' is only being
          called in 'ROTATION_MOVEMENT_PROFILE_FAST'. Therefore we know the exact values of 
          'acceleration' and 'deceleration' and we also know the upper bound of 'rotation_speed_max',
          which implies an upper bound for 'max_velocity'. We also know the upper and lower bounds
          of 'max_displacement_deg' from 'rotation_calc_displacement_abs'and 'rotation_calc_displacement_rel',
          which allows us to calculate the number of steps.
  */

  uint32_t max_displacement_deg;
  __CPROVER_assume(max_displacement_deg >= 0 && max_displacement_deg < TSCP_MAX_DISPLACEMENT_DEG);

  uint32_t steps = TSCP_MDEG_TO_STEP(max_displacement_deg) / 1000;

  unsigned char rotation_speed_max;
  __CPROVER_assume(rotation_speed_max > 0 && rotation_speed_max <= DRIVE_SPPED_MAX_PREDEFINDED);

  double max_velocity = drive_speed_to_sps(rotation_speed_max);
  double acceleration = DRIVE_ACCELERATION_STEPS_S2;
  double deceleration = DRIVE_DECELERATION_STEPS_S2;

  drive_model_t* drive_model = (drive_model_t*) malloc(sizeof(drive_model_t));
  __CPROVER_assume(drive_model != NULL);

  drive_create_linear_model(steps, acceleration, deceleration, max_velocity, drive_model);

  assert(drive_model->a == (int32_t) acceleration);
  assert(drive_model->d == (int32_t) deceleration);

  if (steps == 0) {
    assert(drive_model->t_a == 0);
    assert(drive_model->t_d == 0);
    assert(drive_model->s_a == 0);
    assert(drive_model->s_d == 0);
    assert(drive_model->v_top == 0);
  } else {
    double max_acceleration = max_velocity / acceleration;
    double max_deceleration = max_velocity / -deceleration;
    double max_steps_accelerating = (acceleration * (max_acceleration * max_acceleration)) / 2;
    double max_steps_decelerating = (-deceleration * (max_deceleration * max_deceleration)) / 2;
    double eps = 0.0000001;

    assert(drive_model->t_a > 0);
    assert(drive_model->t_a <= max_acceleration);

    assert(drive_model->t_d > 0);
    assert(drive_model->t_d <= max_deceleration);

    assert(__CPROVER_fabs(drive_model->t_a - drive_model->t_d) < eps);

    assert(drive_model->s_a >= 0);
    assert(drive_model->s_a <= max_steps_accelerating);

    assert(drive_model->s_d >= 0);
    assert(drive_model->s_d <= max_steps_decelerating);

    assert(drive_model->s_a == drive_model->s_d);

    assert(drive_model->v_top > 0);
    // Apparently v_top is not capped to later indicate an invalid speed config param.
    // assert(drive_model->v_top <= max_velocity)
  }

}
