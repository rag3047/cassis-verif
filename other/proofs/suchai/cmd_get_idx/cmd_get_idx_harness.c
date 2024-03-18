// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

/*
 * Insert copyright notice
 */

/**
 * @file cmd_get_idx_harness.c
 * @brief Implements the proof harness for cmd_get_idx function.
 */

/*
 * Insert project header files that
 *   - include the declaration of the function
 *   - include the types needed to declare function arguments
 */

#include "suchai/repoCommand.h"

extern cmd_list_t cmd_list[SCH_CMD_MAX_ENTRIES];

// Noop logging function used to suppress logging related errors
void log_noop(const char *lvl, const char *tag, const char *msg, ...) {}

void harness(void)
{
  // set log function to suppress logging related dereferencing errors, since
  // we don't want to include the whole 'log_init' call stack in this proof.
  log_function = log_noop;

  // somehow this function is included in the coverage report, even though it
  // is not used... calling it here explicitly allows us to get 100% coverage.
  cmd_null("", "", 0);

  __CPROVER_havoc_object(cmd_list);

  int index;
  __CPROVER_assume(index >= 0);

  cmd_t* cmd = cmd_get_idx(index);

  if (index > SCH_CMD_MAX_ENTRIES) {
    assert(cmd == NULL);
  }

  if (cmd != NULL) {
    assert(cmd->id == index);
    assert(cmd->function == cmd_list[index].function);
    assert(cmd->nparams == cmd_list[index].nparams);
    assert(cmd->params == NULL);
  }
}
