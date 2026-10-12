// SPDX-License-Identifier: MIT
#define _GNU_SOURCE

/* Destructive device tests. Run only on an idle memory-only test instance. */
#include <errno.h>
#include <fcntl.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>

#include "simple_char_ioctl.h"

static void require(bool condition, const char *message)
{
	if (!condition) {
		fprintf(stderr, "FAIL: %s (errno=%d: %s)\n", message, errno, strerror(errno));
		exit(EXIT_FAILURE);
	}
}

static struct simple_char_stats stats(int fd)
{
	struct simple_char_stats value = { 0 };

	require(ioctl(fd, SIMPLE_CHAR_IOC_GET_STATS, &value) == 0, "GET_STATS");
	return value;
}

static void fault_case(int fd, unsigned char *page, size_t page_size,
		       bool writing, bool partial)
{
	unsigned char seed[128];
	unsigned char actual[128];
	unsigned char *user = page + page_size - (partial ? 32U : 0U);
	struct simple_char_stats before, after;
	ssize_t result;
	size_t copied, index;
	int saved_errno;

	memset(seed, 'O', sizeof(seed));
	memset(page, 'X', page_size);
	require(ioctl(fd, SIMPLE_CHAR_IOC_CLEAR) == 0, "CLEAR");
	require(pwrite(fd, seed, sizeof(seed), 0) == (ssize_t)sizeof(seed), "seed write");
	require(lseek(fd, 7, SEEK_SET) == 7, "seek before fault");
	before = stats(fd);
	errno = 0;
	result = writing ? write(fd, user, 64) : read(fd, user, 64);
	saved_errno = errno;
	/* Copy helpers may return no prefix, depending on architecture/copy path. */
	require((result == -1 && saved_errno == EFAULT) ||
		(partial && result > 0 && result <= 32), "short I/O or EFAULT");
	copied = result > 0 ? (size_t)result : 0;
	require(lseek(fd, 0, SEEK_CUR) == (off_t)(7 + copied), "position tracks prefix");
	after = stats(fd);
	require(after.last_error == -EFAULT, "last_error records EFAULT");
	require(after.data_size == sizeof(seed), "fault preserves logical length");
	require(after.write_ops == before.write_ops + (writing && copied ? 1U : 0U),
		"write operation count");
	require(after.read_ops == before.read_ops + (!writing && copied ? 1U : 0U),
		"read operation count");
	require(after.bytes_written == before.bytes_written + (writing ? copied : 0),
		"written byte count");
	require(after.bytes_read == before.bytes_read + (writing ? 0 : copied),
		"read byte count");
	if (writing)
		memset(seed + 7, 'X', copied);
	else
		for (index = 0; index < copied; index++)
			require(user[index] == 'O', "read prefix content");
	require(pread(fd, actual, sizeof(actual), 0) == (ssize_t)sizeof(actual), "read back");
	require(memcmp(actual, seed, sizeof(seed)) == 0, "uncopied live data is unchanged");
	printf("PASS: %s %s user-copy fault; committed=%zu\n",
	       partial ? "cross-page" : "fully inaccessible", writing ? "write" : "read", copied);
}

int main(int argc, char **argv)
{
	long page_size = sysconf(_SC_PAGESIZE);
	unsigned char *pages;
	struct simple_char_stats initial;
	int fd;

	if (argc != 3 || strcmp(argv[2], "--allow-clear") != 0) {
		fprintf(stderr, "Usage: %s DEVICE --allow-clear (erases the shared buffer)\n", argv[0]);
		return EXIT_FAILURE;
	}
	require(page_size > 0, "page size");
	fd = open(argv[1], O_RDWR | O_CLOEXEC);
	require(fd >= 0, "open device");
	initial = stats(fd);
	require(!initial.gpio_enabled && !initial.i2c_enabled && initial.capacity >= 128,
		"requires disabled hardware and capacity >= 128");
	pages = mmap(NULL, (size_t)page_size * 2, PROT_READ | PROT_WRITE,
		     MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
	require(pages != MAP_FAILED, "mmap");
	require(mprotect(pages + page_size, (size_t)page_size, PROT_NONE) == 0, "mprotect");
	fault_case(fd, pages, (size_t)page_size, true, false);
	fault_case(fd, pages, (size_t)page_size, true, true);
	fault_case(fd, pages, (size_t)page_size, false, false);
	fault_case(fd, pages, (size_t)page_size, false, true);
	require(ioctl(fd, SIMPLE_CHAR_IOC_CLEAR) == 0, "final CLEAR");
	require(munmap(pages, (size_t)page_size * 2) == 0, "munmap");
	require(close(fd) == 0, "close");
	puts("PASS: all four user-copy fault cases");
	return EXIT_SUCCESS;
}
