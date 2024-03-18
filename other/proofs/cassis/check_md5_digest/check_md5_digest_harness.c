// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

/*
 * Insert copyright notice
 */

/**
 * @file check_md5_digest_harness.c
 * @brief Implements the proof harness for check_md5_digest function.
 */

/*
 * Insert project header files that
 *   - include the declaration of the function
 *   - include the types needed to declare function arguments
 */

#include <assert.h>
#include "helpers/cassis_utilities.h"

/**
 * @brief Starting point for formal analysis
 * 
 */
void harness(void)
{

  /* Insert argument declarations */

  unsigned char d1[MD5_DIGEST_LENGTH];
  __CPROVER_havoc_object(d1);

  unsigned char d2[MD5_DIGEST_LENGTH];
  __CPROVER_havoc_object(d2);

  int result = check_md5_digest((unsigned char*) &d1, (unsigned char*) &d2);

  if (__CPROVER_array_equal(d1, d2)) {
    assert(result == 0);
  } else {
    assert(result < 0);
  }
}
