// SPDX-License-Identifier: MIT
/* Emit ABI values and wire payloads from the actual public C header. */
#include <stddef.h>
#include <stdio.h>

#include "simple_char_ioctl.h"

static void print_hex(const void *payload, size_t size)
{
	const unsigned char *bytes = payload;
	size_t index;

	for (index = 0; index < size; index++)
		printf("%02x", (unsigned int)bytes[index]);
}

int main(void)
{
	const struct simple_char_stats stats = {
		.open_count = 0x100000001ULL,
		.read_ops = 0x200000002ULL,
		.write_ops = 0x300000003ULL,
		.bytes_read = 0x400000004ULL,
		.bytes_written = 0x500000005ULL,
		.data_size = 123,
		.capacity = 4096,
		.open_handles = 7,
		.last_error = -28,
		/* Unique layout-only sentinels, not observed device/hardware values. */
		.gpio_enabled = 11,
		.gpio_value = 12,
		.i2c_enabled = 13,
		.reserved = 14,
	};
	const struct simple_char_gpio_request gpio = { .value = 1 };
	const struct simple_char_i2c_request i2c = { .reg = 0xab, .value = 0xcd };

	printf("{\n"
	       "  \"stats_size\": %zu,\n"
	       "  \"gpio_size\": %zu,\n"
	       "  \"i2c_size\": %zu,\n"
	       "  \"get_stats\": %lu,\n"
	       "  \"clear\": %lu,\n"
	       "  \"gpio_set\": %lu,\n"
	       "  \"i2c_write_reg\": %lu,\n"
	       "  \"stats_hex\": \"",
	       sizeof(stats), sizeof(gpio), sizeof(i2c),
	       (unsigned long)SIMPLE_CHAR_IOC_GET_STATS,
	       (unsigned long)SIMPLE_CHAR_IOC_CLEAR,
	       (unsigned long)SIMPLE_CHAR_IOC_GPIO_SET,
	       (unsigned long)SIMPLE_CHAR_IOC_I2C_WRITE_REG);
	print_hex(&stats, sizeof(stats));
	printf("\",\n  \"gpio_hex\": \"");
	print_hex(&gpio, sizeof(gpio));
	printf("\",\n  \"i2c_hex\": \"");
	print_hex(&i2c, sizeof(i2c));
	printf("\"\n}\n");
	return ferror(stdout) ? 1 : 0;
}
