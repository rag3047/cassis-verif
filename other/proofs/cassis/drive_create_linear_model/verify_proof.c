/*
    Note: This code is used to double-check the outcome of the drive_create_linear_model proof.
    Use the following command to compile the code:

        gcc -o verify_proof verify_proof.c -lm

    Running the 'verify_proof' executable will confirm that indeed, there is a difference between the number of steps during
    acceleration and deceleration.
*/

#include <stdint.h>
#include <stdio.h>

#define DRIVE_ACCELERATION_STEPS_S2 (+2381.0) // steps/s^2 (23.81 turns/s in 1 sec)
#define DRIVE_DECELERATION_STEPS_S2 (-2381.0) // steps/s^2 (23.81 turns/s in 1 sec)

/**
 * @brief Motion profile used by rotate fast.
 */
typedef struct
{
    int32_t a;    //!< acceleration [steps/s^2]
    int32_t d;    //!< deceleration [steps/s^2] (negative)
    double t_a;   //!< acceleration time in seconds.
    double t_d;   //!< deceleration time in seconds.
    uint32_t s_a; //!< # steps covered during acceleration.
    uint32_t s_d; //!< # steps covered during deceleration.
    double v_top; //!< top speed reached [steps/s]
} drive_model_t;

/**
 * @brief Calculates acceleration, deceleration and constant speed times.
 * @param steps Total number of steps to move (distance).
 * @param a acceleration [steps/s^2]
 * @param d deceleration [steps/s^2]
 * @param v_max Maximum allowed speed [steps/s]
 * @param[out] model Pointer to memory where the calculated profile is stored.
 *
 * @author Mario Gruber
 */
void drive_create_linear_model(uint32_t steps, double a, double d, double v_max, drive_model_t *model)
{
    model->a = a;
    model->d = d;

    /**
     * compute acceleration and deceleration times without limiting the velocity
     * to check if we reach v_max at all
     */
    double t_a = __builtin_sqrt((-2.0 * d * steps) / (a * (a - d)));
    double t_d = (t_a * a) / (-1.0 * d);

    /* top speed */
    double v_top = t_a * a;

    if (v_top > v_max)
    {
        /* cap acceleration and adjust deceleration */
        t_a = (double)v_max / a;
        t_d = (double)v_max / -d;
    }

    model->v_top = v_top;

    model->t_a = t_a;
    model->t_d = t_d;

    /* compute distances */
    model->s_a = (a * (t_a * t_a)) / 2;
    model->s_d = (-d * (t_d * t_d)) / 2;
}

void main()
{
    uint32_t steps = 594;
    double acceleration = DRIVE_ACCELERATION_STEPS_S2;
    double deceleration = DRIVE_DECELERATION_STEPS_S2;
    double v_max = 2125.0;

    drive_model_t model;

    drive_create_linear_model(steps, acceleration, deceleration, v_max, &model);

    printf("a: %d\n", model.a);
    printf("d: %d\n", model.d);
    printf("t_a: %f\n", model.t_a);
    printf("t_d: %f\n", model.t_d);
    printf("s_a: %u\n", model.s_a);
    printf("s_d: %u\n", model.s_d);
    printf("v_top: %f\n", model.v_top);
}