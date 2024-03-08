
#include <stdio.h>
#include <stdint.h>

#define GDS_NUMBER_OF_PARAMETER_TABLES 32
#define GDS_NUMBER_OF_IMAGING_PARAMS 32
#define CMDTAB_MAX_SCRIPT_COMMANDS 32
#define GDS_MAX_NUMBER_OF_HK_PARAMS 128
#define GDS_NUMBER_OF_CONFIG_PARAMETERS 32

struct gds_command_parameter_t
{
    // size: 16 Byte
    union
    {
        struct
        {
            uint64_t v;
        } v64;
        struct
        {
            uint32_t v_overflow[1];
            uint32_t v;
        } v32;
        struct
        {
            uint16_t v_overflow[3];
            uint16_t v;
        } v16;
        struct
        {
            unsigned char v_overflow[7];
            unsigned char v;
        } v8;

        uint64_t ptr64[1];
        uint32_t ptr32[2];
        uint16_t ptr16[4];
        unsigned char ptr8[8];
    } value;
    unsigned char id;         // command parameter id (tag)
    unsigned char reference;  // type of parameter reference (input-paramtable-...)
    unsigned char source_id;  // used in script commands parameter: the tag of the source parameter in script command
    unsigned char a_overflow; // TODO: for proper memory alignment?
    uint32_t ai_overflow;     // TODO: for proper memory alignment?
};

// HK table entry
struct gds_hk_table_entry_t
{
    //	uint64_t ptr64[1];
    //	uint32_t ptr32[2];
    //	uint16_t ptr16[4];
    union
    {
        struct
        {
            uint64_t v;
        } v64;
        struct
        {
            uint32_t v_overflow[1];
            uint32_t v;
        } v32;
        struct
        {
            uint16_t v_overflow[3];
            uint16_t v;
        } v16;
        struct
        {
            unsigned char v_overflow[7];
            unsigned char v;
        } v8;
        unsigned char ptr8[8];
        uint16_t ptr16[4];
    } value;
    unsigned char tag;
    unsigned char length;
    unsigned char vtype;
    unsigned char persist;
    unsigned char enable_update;
};

// HK table
struct gds_hk_table_t
{
    unsigned char num_params;
    struct gds_hk_table_entry_t parameters[GDS_MAX_NUMBER_OF_HK_PARAMS];
};
// Config table
struct gds_cfg_table_t
{
    unsigned char num_params;
    struct gds_hk_table_entry_t parameters[GDS_NUMBER_OF_CONFIG_PARAMETERS];
};
// Parameter table
struct gds_parameter_table_t
{
    unsigned char id;
    unsigned char num_params;
    struct gds_hk_table_entry_t parameters[GDS_NUMBER_OF_IMAGING_PARAMS];
};

// number of majority votes
#define BM_MAJORITY_VOTE_COUNT 3
#define BM_MAJORITY_VOTE_ALIGN 4
// min accept number for majority voting
#define BM_MAJORITY_ACCEPT_MIN 2

struct gds_persistent_hk_t
{
    uint16_t z1_min[BM_MAJORITY_VOTE_ALIGN];
    uint16_t z1_max[BM_MAJORITY_VOTE_ALIGN];
    uint16_t z2_min[BM_MAJORITY_VOTE_ALIGN];
    uint16_t z2_max[BM_MAJORITY_VOTE_ALIGN];
    uint16_t z3_min[BM_MAJORITY_VOTE_ALIGN];
    uint16_t z3_max[BM_MAJORITY_VOTE_ALIGN];
    uint16_t z31_min[BM_MAJORITY_VOTE_ALIGN];
    uint16_t z31_max[BM_MAJORITY_VOTE_ALIGN];
    uint16_t z4_min[BM_MAJORITY_VOTE_ALIGN];
    uint16_t z4_max[BM_MAJORITY_VOTE_ALIGN];
    uint16_t z41_min[BM_MAJORITY_VOTE_ALIGN];
    uint16_t z41_max[BM_MAJORITY_VOTE_ALIGN];
    uint16_t z5_min[BM_MAJORITY_VOTE_ALIGN];
    uint16_t z5_max[BM_MAJORITY_VOTE_ALIGN];
    uint32_t last_position[BM_MAJORITY_VOTE_COUNT];
    uint32_t requested_position[BM_MAJORITY_VOTE_COUNT];
    unsigned char rotatesw_health[BM_MAJORITY_VOTE_ALIGN];
    unsigned char fsw_last_mode[BM_MAJORITY_VOTE_ALIGN];
    unsigned char fsw_recovery[BM_MAJORITY_VOTE_ALIGN];
    //	unsigned char padding[3];
    //	uint16_t crc;
};

#define CMDTAB_MAX_ATOMIC_PARAM 40
// Script command table
struct gds_script_command_t
{
    // size: 16B*40 + 8B = 648 B
    struct gds_command_parameter_t parameters[CMDTAB_MAX_ATOMIC_PARAM];
    uint32_t timestamp_offset;
    unsigned char command_code;
    unsigned char num_parameters;
    unsigned char a_overflow[2];
};

#define CMDTAB_MAX_ATOMIC_SCRIPT_COMMANDS 20
struct gds_script_command_table_t
{
    // size: 648B*20 + 8 = 12968 B
    struct gds_script_command_t commands[CMDTAB_MAX_ATOMIC_SCRIPT_COMMANDS];
    int num_commands;
    unsigned char script_code;
    unsigned char permission;
};

struct thermal_pid_t
{
    //	uint16_t f_err[THERMAL_ERROR_FUNCT_LEGTH];
    int err;
    int acc_ierr;
    int last_derr;
    // int16_t heater_pwm;
    int kp;
    int ki;
    int kd;
    int q;
};

typedef struct
{
    unsigned char rCtrl;
    unsigned char rStatus;
    unsigned char rPwm;
    unsigned char rSetTemp;

} volatile fpga_heater_regs_t;

struct thermal_zone_t
{
    uint16_t sensor_health;
    // uint16_t sensor_weight_sum;
    unsigned char sensor_hk_tag[8];
    unsigned char sensor_weight[8];
    fpga_heater_regs_t *heater;
    unsigned char heater_health[2];
    uint16_t heater_resistance_mul10[2];
    unsigned char calc_temp_tag;
    unsigned char targ_min_temp_tag;
    unsigned char targ_max_temp_tag;
    unsigned char zone_control_type;

    //	unsigned char zone_id;
    struct thermal_pid_t pid;
};

#define THERMAL_MAX_THERM_ZONES 16
struct thermal_zones_config_t
{
    struct thermal_zone_t thermal_zones[THERMAL_MAX_THERM_ZONES];
    unsigned char num_zones;
};

struct gds_persistent_storage_t
{
    uint32_t ptrn;
    uint32_t version[BM_MAJORITY_VOTE_COUNT];
    uint32_t state_votes[BM_MAJORITY_VOTE_COUNT];
    uint32_t script_table_dirty;
    struct gds_script_command_table_t script_table[CMDTAB_MAX_SCRIPT_COMMANDS];
    unsigned char script_table_digest[16];
    uint32_t parameter_table_dirty;
    struct gds_parameter_table_t parameter_tables[GDS_NUMBER_OF_PARAMETER_TABLES];
    unsigned char paramter_table_digest[16];
    uint32_t hk_dirty;
    struct gds_persistent_hk_t hk;
    uint32_t config_params_dirty;
    struct gds_cfg_table_t config_params;
    unsigned char config_params_digest[16];
    uint32_t thermal_config_dirty;
    struct thermal_zones_config_t thermal_config;
    unsigned char thermal_config_digest[16];
    // struct gds_persistent_hk_t hk_mirror;
    unsigned char digest[16];
};

struct gds_parameter_table_t parameter_tables[GDS_NUMBER_OF_PARAMETER_TABLES];

void main()
{
    printf("parameter_tables: %lu bytes\n", sizeof(parameter_tables));
    printf("pesistent_storage: %lu bytes\n", sizeof(struct gds_persistent_storage_t));
    printf("total: %lu bytes\n", (sizeof(parameter_tables) + sizeof(struct gds_persistent_storage_t)));
}