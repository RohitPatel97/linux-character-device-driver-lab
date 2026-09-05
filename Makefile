KDIR ?= /lib/modules/$(shell uname -r)/build
PYTHON ?= python3
MODULE_DIR := $(CURDIR)/kernel

.PHONY: all module client test check clean help

all: module client

module:
	@test -d "$(KDIR)" || { \
		echo "Kernel build directory not found: $(KDIR)" >&2; \
		echo "Install matching kernel headers or run: make module KDIR=/path/to/headers" >&2; \
		exit 2; \
	}
	$(MAKE) -C "$(KDIR)" M="$(MODULE_DIR)" modules

client:
	$(MAKE) -C user

test:
	PYTHONPATH="$(CURDIR)" $(PYTHON) -m unittest discover -s tests -v

check: client test
	bash ./scripts/check-shell.sh

clean:
	@if test -d "$(KDIR)"; then \
		$(MAKE) -C "$(KDIR)" M="$(MODULE_DIR)" clean; \
	else \
		find kernel -maxdepth 1 -type f \
			\( -name '*.o' -o -name '*.ko' -o -name '*.mod*' -o -name '*.cmd' \
			-o -name 'modules.order' -o -name 'Module.symvers' \) -delete; \
	fi
	$(MAKE) -C user clean
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

help:
	@echo "Targets:"
	@echo "  module  Build simple_char.ko (KDIR may be overridden)"
	@echo "  client  Build the C user-space CLI"
	@echo "  test    Run host-only Python tests (no root/module required)"
	@echo "  check   Build the client and run all host-only checks"
	@echo "  clean   Remove generated artifacts"
