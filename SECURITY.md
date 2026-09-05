# Security policy

## Supported versions

Security fixes are applied to the latest release and the default branch.

## Reporting

Do not publish an exploit, unsafe wiring instruction, or sensitive host log in a
public issue. Contact the repository owner privately first, with a minimal
reproducer, affected kernel/configuration, impact, and suggested mitigation.

## Threat model

The driver assumes device-node access is limited to trusted local users. It
does not isolate data between users. GPIO/I2C actions require `CAP_SYS_RAWIO`
and explicit load-time opt-in. The code intentionally exposes no raw kernel
addresses, arbitrary bus messages, debugfs state, or world-writable udev rule.

Treat out-of-tree kernel code as privileged code: review it, build it from a
known commit, validate signatures where Secure Boot is used, and test on a
disposable system before production or physical-hardware use.

