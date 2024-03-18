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

#include <stdint.h>
#include <stdio.h>
#include <assert.h>
#include "cassis_global_datastorage.h"
#include "helpers/cassis_utilities.h"

int generate_md5_digest(unsigned char *in_buff, int in_len, unsigned char* digest) {
  assert(__CPROVER_r_ok(in_buff, in_len));
  assert(__CPROVER_w_ok(digest, MD5_DIGEST_LENGTH));

  __CPROVER_havoc_object(digest);

  return MD5_DIGEST_LENGTH;
}

// struct gds_persistent_storage_t *gds_persistent_storage = (void *)GDS_ADDRESS_PERSISTENT_STORAGE;
extern struct gds_persistent_storage_t *gds_persistent_storage;
extern struct gds_parameter_table_t parameter_tables[GDS_NUMBER_OF_PARAMETER_TABLES];

void harness(void)
{
  // workaround for modelling the non-volatile memory region
  gds_persistent_storage = (struct gds_persistent_storage_t *) malloc(sizeof(struct gds_persistent_storage_t));
  __CPROVER_assume(gds_persistent_storage != NULL);

  __CPROVER_havoc_object(gds_persistent_storage);
  __CPROVER_havoc_object(parameter_tables);

  gds_persist_ptables();

  assert(__CPROVER_array_equal(gds_persistent_storage->parameter_tables, parameter_tables));
  assert(gds_persistent_storage->parameter_table_dirty == 0x00000000);
}
