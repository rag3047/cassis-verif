// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

/*
 * Insert copyright notice
 */

/**
 * @file supervisor_get_scheduled_commands_harness.c
 * @brief Implements the proof harness for supervisor_get_scheduled_commands function.
 */

/*
 * Insert project header files that
 *   - include the declaration of the function
 *   - include the types needed to declare function arguments
 */

#include <stdlib.h>
#include <stdint.h>
#include <assert.h>
#include "cassis_supervisor_internal.h"
#include "cassis_cmdscript_interpreter.h"

// Note: Modify cassis_cmdscript_interpreter.h: set CMDTAB_MAX_ATOMIC_COMMANDS to 10, to make sure the proof finishes faster

// since we don't have a header file, we just add a forward definition.
void supervisor_get_scheduled_commands(uint64_t scheduleTS, struct gds_atomic_command_t **ts_command, int *ts_cnt, struct gds_atomic_command_t **command, int *cnt);

// generate nondet uint64
uint64_t nondet_uint64();
// holds a preissue timestamp for every command, allows mapping command ptr to preissue timestamp
uint64_t preissue_ts_lookup_table[CMDTAB_MAX_ATOMIC_COMMANDS];

/*
  Initialize command_table and nondet choose number of pending commands.
  Also count number of pending commands (total, with and without timestamp).
*/
void command_table_init(uint64_t scheduleTS, uint32_t* num_no_ts_commands, uint32_t* num_pending_commands, uint32_t* num_ts_commands) {
  __CPROVER_havoc_object(&command_table);

  uint32_t _no_timestamp = 0;
  uint32_t _pending = 0;
  uint32_t _timestamp = 0;

  for (int i = 0; i < CMDTAB_MAX_ATOMIC_COMMANDS; i++) {
    // count number of entries generated
    if (command_table.commands[i].status == CMDTAB_COMMAND_STATUS_PENDING) {
      _pending++;

      if (command_table.commands[i].timestamp == 0) {
        _no_timestamp++;
      } else {
        // populate lookup table with preissue timestamps
        preissue_ts_lookup_table[i] = nondet_uint64();
        __CPROVER_assume(preissue_ts_lookup_table[i] > 0 && preissue_ts_lookup_table[i] <= command_table.commands[i].timestamp);

        if (preissue_ts_lookup_table[i] < scheduleTS) {
          _timestamp++;
        }
      }
    }
  }

  *num_pending_commands = _pending;
  *num_no_ts_commands = _no_timestamp;
  *num_ts_commands = _timestamp;
}

uint64_t get_preissue_timestamp(struct gds_atomic_command_t *command) {
  if (command == NULL) return 0;

  struct gds_atomic_command_t *base_ptr = (struct gds_atomic_command_t *) &command_table.commands;
  uint64_t index = command - base_ptr;
  
  assert(index >= 0 && index < CMDTAB_MAX_ATOMIC_COMMANDS);
  return preissue_ts_lookup_table[index];
}

/**
 * @brief Starting point for formal analysis
 * 
 */
void harness(void)
{
  #if CMDTAB_MAX_ATOMIC_COMMANDS > 10
  
  // mark proof as failed and early exit if CMDTAB_MAX_ATOMIC_COMMANDS is too large,
  // because it will cause the proof to run for several days
  assert(false);
  return;

  #endif /* CMDTAB_MAX_ATOMIC_COMMANDS > 10 */

  // counters for command table initialization
  uint32_t num_pending_commands = 0;
  uint32_t num_no_ts_commands = 0;
  uint32_t num_ts_commands = 0;

  // nondet choose timestamp
  uint64_t scheduleTS;
  int ts_cnt;
  int cnt;

  // nondet initialize command queues
  __CPROVER_havoc_object(scheduled_commands);
  __CPROVER_havoc_object(scheduled_ts_commands);

  // initialize command_table
  command_table_init(scheduleTS, &num_no_ts_commands, &num_pending_commands, &num_ts_commands);

  supervisor_get_scheduled_commands(scheduleTS, scheduled_ts_commands, &ts_cnt, scheduled_commands, &cnt);

  // check that the returned counts correspond to what was nondet initialized by cbmc
  assert(cnt == num_no_ts_commands);
  assert(ts_cnt == num_ts_commands);
  assert(ts_cnt + cnt <= num_pending_commands);

  // check command queues
  for (int i = 0; i < cnt; i++) {
    assert(scheduled_commands[i]->status == CMDTAB_COMMAND_STATUS_PENDING);
    assert(scheduled_commands[i]->timestamp == 0);
  }

  for (int i = 0; i < ts_cnt; i++) {
    assert(scheduled_ts_commands[i]->status == CMDTAB_COMMAND_STATUS_PENDING);
    assert(scheduled_ts_commands[i]->timestamp > 0);
    assert(get_preissue_timestamp(scheduled_ts_commands[i]) < scheduleTS);
  }
}
