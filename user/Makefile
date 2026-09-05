CC ?= cc
CPPFLAGS ?= -I../include/uapi
CFLAGS ?= -O2 -g
CFLAGS += -std=c11 -Wall -Wextra -Wpedantic -Wconversion -Wshadow
TARGET := simple-char-cli

.PHONY: all clean

all: $(TARGET)

$(TARGET): simple_char_cli.c ../include/uapi/simple_char_ioctl.h
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ simple_char_cli.c

clean:
	$(RM) $(TARGET)

