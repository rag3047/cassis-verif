// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

/*
 * Insert copyright notice
 */

/**
 * @file gds_persist_ptables_harness.c
 * @brief Implements the proof harness for gds_persist_ptables function.
 */

/*
 * Insert project header files that
 *   - include the declaration of the function
 *   - include the types needed to declare function arguments
 */

// #include <string.h>
#include <stdint.h>
#include <stdio.h>
#include <assert.h>
#include "cassis_global_datastorage.h"
#include "helpers/cassis_utilities.h"

// Generate the same nondet byte given the same inputs
unsigned char __CPROVER_uninterpreted_byte(unsigned char* in_buff, int in_len, int index);

void internal_generate_md5_digest(unsigned char* in_buff, int in_len, unsigned char* digest) {
  for (int i = 0; i < MD5_DIGEST_LENGTH; i++) {
    digest[i] = __CPROVER_uninterpreted_byte(in_buff, in_len, i);
  }
}

inline int generate_md5_digest(unsigned char *in_buff, int in_len, unsigned char* digest) {
  assert(__CPROVER_r_ok(in_buff, in_len));
  assert(__CPROVER_rw_ok(digest, MD5_DIGEST_LENGTH));
  internal_generate_md5_digest(in_buff, in_len, digest);
}

struct gds_persistent_storage_t *gds_persistent_storage = (void *)GDS_ADDRESS_PERSISTENT_STORAGE;
struct gds_parameter_table_t parameter_tables[GDS_NUMBER_OF_PARAMETER_TABLES];

/**
 * @brief Starting point for formal analysis
 * 
 */
void harness(void)
{
  __CPROVER_havoc_object(gds_persistent_storage);
  __CPROVER_havoc_object(parameter_tables);

  unsigned char md5[MD5_DIGEST_LENGTH];
  internal_generate_md5_digest((unsigned char *)gds_persistent_storage->parameter_tables, sizeof(parameter_tables), gds_persistent_storage->paramter_table_digest);

  gds_persist_ptables();

  assert(__CPROVER_array_equal(gds_persistent_storage->parameter_tables, parameter_tables));
  assert(gds_persistent_storage->parameter_table_dirty == 0x00000000);
  assert(__CPROVER_array_equal(gds_persistent_storage->paramter_table_digest, md5));
}
