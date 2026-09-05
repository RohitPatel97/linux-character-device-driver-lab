/* SPDX-License-Identifier: MIT */
#ifndef SIMPLE_CHAR_IOCTL_H
#define SIMPLE_CHAR_IOCTL_H

#include <linux/ioctl.h>
#include <linux/types.h>

#define SIMPLE_CHAR_DEVICE_NAME "simple_char"
#define SIMPLE_CHAR_IOC_MAGIC 0xB7

/*
 * The fixed-width layout deliberately avoids pointer-sized fields so the same
 * ABI works for 32-bit user space on a 64-bit kernel.
 */
struct simple_char_stats {
	__u64 open_count;
	__u64 read_ops;
	__u64 write_ops;
	__u64 bytes_read;
	__u64 bytes_written;
	__u32 data_size;
	__u32 capacity;
	__s32 open_handles;
	__s32 last_error;
	__u32 gpio_enabled;
	__u32 gpio_value;
	__u32 i2c_enabled;
	__u32 reserved;
};

struct simple_char_gpio_request {
	__u32 value;
};

struct simple_char_i2c_request {
	__u32 reg;
	__u32 value;
};

#define SIMPLE_CHAR_IOC_GET_STATS \
	_IOR(SIMPLE_CHAR_IOC_MAGIC, 0x01, struct simple_char_stats)
#define SIMPLE_CHAR_IOC_CLEAR _IO(SIMPLE_CHAR_IOC_MAGIC, 0x02)
#define SIMPLE_CHAR_IOC_GPIO_SET \
	_IOW(SIMPLE_CHAR_IOC_MAGIC, 0x03, struct simple_char_gpio_request)
#define SIMPLE_CHAR_IOC_I2C_WRITE_REG \
	_IOW(SIMPLE_CHAR_IOC_MAGIC, 0x04, struct simple_char_i2c_request)

#define SIMPLE_CHAR_IOC_MAX_NR 0x04

#endif /* SIMPLE_CHAR_IOCTL_H */
