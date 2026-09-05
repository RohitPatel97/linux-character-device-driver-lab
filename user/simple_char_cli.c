// SPDX-License-Identifier: MIT
#define _POSIX_C_SOURCE 200809L

#include <errno.h>
#include <fcntl.h>
#include <getopt.h>
#include <inttypes.h>
#include <limits.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#include "simple_char_ioctl.h"

#define DEFAULT_DEVICE "/dev/simple_char"
#define DEFAULT_READ_SIZE 4096U

_Static_assert(sizeof(struct simple_char_stats) == 72,
	       "simple_char_stats ABI size changed");

static void usage(FILE *stream, const char *program)
{
	fprintf(stream,
		"Usage: %s [-d DEVICE] COMMAND [ARGUMENTS]\n"
		"\n"
		"Commands:\n"
		"  write TEXT          Write TEXT at offset zero\n"
		"  read [COUNT]        Read up to COUNT bytes (default: 4096)\n"
		"  roundtrip TEXT      Clear, write, seek, read, and compare\n"
		"  stats               Print driver counters as JSON\n"
		"  clear               Zero the buffer and reset its length\n"
		"  gpio 0|1            Set the opt-in GPIO hook\n"
		"  i2c REG VALUE       Write an 8-bit I2C register (base 0)\n"
		"\n"
		"Options:\n"
		"  -d, --device PATH   Device node (default: %s)\n"
		"  -h, --help          Show this help\n",
		program, DEFAULT_DEVICE);
}

static int parse_u32(const char *text, uint32_t maximum, uint32_t *value)
{
	char *end = NULL;
	unsigned long parsed;

	errno = 0;
	parsed = strtoul(text, &end, 0);
	if (errno != 0 || end == text || *end != '\0' || parsed > maximum)
		return -1;
	*value = (uint32_t)parsed;
	return 0;
}

static int open_device(const char *path, int flags)
{
	int descriptor;

	do {
		descriptor = open(path, flags | O_CLOEXEC);
	} while (descriptor < 0 && errno == EINTR);

	if (descriptor < 0)
		fprintf(stderr, "open %s: %s\n", path, strerror(errno));
	return descriptor;
}

static int seek_to_start(int descriptor)
{
	if (lseek(descriptor, 0, SEEK_SET) < 0) {
		fprintf(stderr, "lseek: %s\n", strerror(errno));
		return -1;
	}
	return 0;
}

static int write_all(int descriptor, const void *buffer, size_t length)
{
	const unsigned char *cursor = buffer;
	size_t remaining = length;

	while (remaining > 0) {
		ssize_t written = write(descriptor, cursor, remaining);

		if (written < 0 && errno == EINTR)
			continue;
		if (written < 0) {
			fprintf(stderr, "write: %s\n", strerror(errno));
			return -1;
		}
		if (written == 0) {
			fprintf(stderr, "write: unexpected zero-byte result\n");
			return -1;
		}
		cursor += (size_t)written;
		remaining -= (size_t)written;
	}
	return 0;
}

static ssize_t read_up_to(int descriptor, void *buffer, size_t capacity)
{
	unsigned char *cursor = buffer;
	size_t total = 0;

	while (total < capacity) {
		ssize_t received = read(descriptor, cursor + total, capacity - total);

		if (received < 0 && errno == EINTR)
			continue;
		if (received < 0) {
			fprintf(stderr, "read: %s\n", strerror(errno));
			return -1;
		}
		if (received == 0)
			break;
		total += (size_t)received;
	}
	if (total > (size_t)SSIZE_MAX) {
		errno = EOVERFLOW;
		return -1;
	}
	return (ssize_t)total;
}

static int command_write(int descriptor, const char *text)
{
	if (seek_to_start(descriptor) < 0)
		return -1;
	return write_all(descriptor, text, strlen(text));
}

static int command_read(int descriptor, size_t count)
{
	unsigned char *buffer;
	ssize_t received;

	buffer = malloc(count == 0 ? 1 : count);
	if (!buffer) {
		fprintf(stderr, "malloc: %s\n", strerror(errno));
		return -1;
	}
	if (seek_to_start(descriptor) < 0) {
		free(buffer);
		return -1;
	}
	received = read_up_to(descriptor, buffer, count);
	if (received >= 0 && write_all(STDOUT_FILENO, buffer, (size_t)received) < 0)
		received = -1;
	free(buffer);
	return received < 0 ? -1 : 0;
}

static int command_roundtrip(int descriptor, const char *text)
{
	size_t length = strlen(text);
	unsigned char *received;
	ssize_t count;

	if (ioctl(descriptor, SIMPLE_CHAR_IOC_CLEAR) < 0) {
		fprintf(stderr, "ioctl CLEAR: %s\n", strerror(errno));
		return -1;
	}
	if (write_all(descriptor, text, length) < 0 || seek_to_start(descriptor) < 0)
		return -1;

	received = malloc(length == 0 ? 1 : length);
	if (!received) {
		fprintf(stderr, "malloc: %s\n", strerror(errno));
		return -1;
	}
	count = read_up_to(descriptor, received, length);
	if (count < 0) {
		free(received);
		return -1;
	}
	if ((size_t)count != length || memcmp(received, text, length) != 0) {
		fprintf(stderr, "roundtrip mismatch: wrote %zu bytes, read %zd\n",
			length, count);
		free(received);
		return -1;
	}
	free(received);
	printf("roundtrip ok: %zu bytes\n", length);
	return 0;
}

static int command_stats(int descriptor)
{
	struct simple_char_stats stats = { 0 };

	if (ioctl(descriptor, SIMPLE_CHAR_IOC_GET_STATS, &stats) < 0) {
		fprintf(stderr, "ioctl GET_STATS: %s\n", strerror(errno));
		return -1;
	}

	printf("{\n"
	       "  \"open_count\": %" PRIu64 ",\n"
	       "  \"open_handles\": %" PRId32 ",\n"
	       "  \"read_ops\": %" PRIu64 ",\n"
	       "  \"write_ops\": %" PRIu64 ",\n"
	       "  \"bytes_read\": %" PRIu64 ",\n"
	       "  \"bytes_written\": %" PRIu64 ",\n"
	       "  \"data_size\": %" PRIu32 ",\n"
	       "  \"capacity\": %" PRIu32 ",\n"
	       "  \"last_error\": %" PRId32 ",\n"
	       "  \"gpio_enabled\": %s,\n"
	       "  \"gpio_value\": %" PRIu32 ",\n"
	       "  \"i2c_enabled\": %s\n"
	       "}\n",
	       (uint64_t)stats.open_count, (int32_t)stats.open_handles,
	       (uint64_t)stats.read_ops, (uint64_t)stats.write_ops,
	       (uint64_t)stats.bytes_read, (uint64_t)stats.bytes_written,
	       (uint32_t)stats.data_size, (uint32_t)stats.capacity,
	       (int32_t)stats.last_error,
	       stats.gpio_enabled ? "true" : "false",
	       (uint32_t)stats.gpio_value,
	       stats.i2c_enabled ? "true" : "false");
	return 0;
}

int main(int argc, char **argv)
{
	static const struct option options[] = {
		{ "device", required_argument, NULL, 'd' },
		{ "help", no_argument, NULL, 'h' },
		{ NULL, 0, NULL, 0 },
	};
	const char *device_path = DEFAULT_DEVICE;
	const char *command;
	uint32_t first;
	uint32_t second;
	size_t read_size = DEFAULT_READ_SIZE;
	int flags = O_RDONLY;
	int descriptor;
	int option;
	int result = -1;

	while ((option = getopt_long(argc, argv, "d:h", options, NULL)) != -1) {
		switch (option) {
		case 'd':
			device_path = optarg;
			break;
		case 'h':
			usage(stdout, argv[0]);
			return EXIT_SUCCESS;
		default:
			usage(stderr, argv[0]);
			return EXIT_FAILURE;
		}
	}

	if (optind >= argc) {
		usage(stderr, argv[0]);
		return EXIT_FAILURE;
	}
	command = argv[optind++];

	if (strcmp(command, "write") == 0 || strcmp(command, "roundtrip") == 0 ||
	    strcmp(command, "clear") == 0 || strcmp(command, "gpio") == 0 ||
	    strcmp(command, "i2c") == 0)
		flags = O_RDWR;

	if (strcmp(command, "read") == 0 && optind < argc) {
		if (parse_u32(argv[optind++], UINT32_MAX, &first) < 0) {
			fprintf(stderr, "invalid read count\n");
			return EXIT_FAILURE;
		}
		read_size = first;
	}
	if (optind < argc && strcmp(command, "write") != 0 &&
	    strcmp(command, "roundtrip") != 0 && strcmp(command, "gpio") != 0 &&
	    strcmp(command, "i2c") != 0) {
		fprintf(stderr, "unexpected argument: %s\n", argv[optind]);
		return EXIT_FAILURE;
	}

	descriptor = open_device(device_path, flags);
	if (descriptor < 0)
		return EXIT_FAILURE;

	if (strcmp(command, "write") == 0 && optind < argc && optind + 1 == argc) {
		result = command_write(descriptor, argv[optind]);
	} else if (strcmp(command, "read") == 0 && optind == argc) {
		result = command_read(descriptor, read_size);
	} else if (strcmp(command, "roundtrip") == 0 && optind < argc &&
		   optind + 1 == argc) {
		result = command_roundtrip(descriptor, argv[optind]);
	} else if (strcmp(command, "stats") == 0 && optind == argc) {
		result = command_stats(descriptor);
	} else if (strcmp(command, "clear") == 0 && optind == argc) {
		result = ioctl(descriptor, SIMPLE_CHAR_IOC_CLEAR) < 0 ? -1 : 0;
		if (result < 0)
			fprintf(stderr, "ioctl CLEAR: %s\n", strerror(errno));
	} else if (strcmp(command, "gpio") == 0 && optind + 1 == argc &&
		   parse_u32(argv[optind], 1, &first) == 0) {
		struct simple_char_gpio_request request = { .value = first };

		result = ioctl(descriptor, SIMPLE_CHAR_IOC_GPIO_SET, &request) < 0 ? -1 : 0;
		if (result < 0)
			fprintf(stderr, "ioctl GPIO_SET: %s\n", strerror(errno));
	} else if (strcmp(command, "i2c") == 0 && optind + 2 == argc &&
		   parse_u32(argv[optind], UINT8_MAX, &first) == 0 &&
		   parse_u32(argv[optind + 1], UINT8_MAX, &second) == 0) {
		struct simple_char_i2c_request request = {
			.reg = first,
			.value = second,
		};

		result = ioctl(descriptor, SIMPLE_CHAR_IOC_I2C_WRITE_REG, &request) < 0 ? -1 : 0;
		if (result < 0)
			fprintf(stderr, "ioctl I2C_WRITE_REG: %s\n", strerror(errno));
	} else {
		fprintf(stderr, "invalid arguments for command '%s'\n", command);
		usage(stderr, argv[0]);
	}

	if (close(descriptor) < 0) {
		fprintf(stderr, "close: %s\n", strerror(errno));
		result = -1;
	}
	return result == 0 ? EXIT_SUCCESS : EXIT_FAILURE;
}

