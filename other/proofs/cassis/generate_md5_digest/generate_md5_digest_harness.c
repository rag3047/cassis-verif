// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

/*
 * Insert copyright notice
 */

/**
 * @file generate_md5_digest_harness.c
 * @brief Implements the proof harness for generate_md5_digest function.
 */

/*
 * Insert project header files that
 *   - include the declaration of the function
 *   - include the types needed to declare function arguments
 */

#include <md5.h>
#include <assert.h>
#include <stdio.h>
#include "helpers/cassis_utilities.h"

// We dont really wanna proof these functions provided by RTEMS RTOS.
// Therefore we just validate function arguments.
void MD5Init(MD5_CTX* ctx) {
  assert(ctx != NULL);
}
void MD5Update(MD5_CTX* ctx, const void* buff, unsigned int len) {
  assert(ctx != NULL);
  assert(__CPROVER_rw_ok(buff, len * sizeof(unsigned char)));
}
void MD5Final(unsigned char hash[MD5_DIGEST_LENGTH], MD5_CTX* ctx) {
  assert(ctx != NULL);
  assert(__CPROVER_rw_ok(hash, MD5_DIGEST_LENGTH * sizeof(unsigned char)));
}

/**
 * @brief Starting point for formal analysis
 * 
 */
void harness(void)
{

  /* Insert argument declarations */

  int in_len;
  // Input Buffer length of 100 is sufficient to get 100% code coverage
  // Therefore there's no need to check larger input sizes.
  __CPROVER_assume(in_len > 0 && in_len <= 100);

  unsigned char in_buff[in_len];
  unsigned char digest[MD5_DIGEST_LENGTH];

  int md5_size = generate_md5_digest((unsigned char*) &in_buff, in_len, (unsigned char*) &digest);
  assert(md5_size == MD5_DIGEST_LENGTH);
}
