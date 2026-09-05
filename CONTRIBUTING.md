# Contributing

Contributions are welcome when they keep the module small, auditable, and safe
to run with hardware disabled.

## Development workflow

1. Create a focused branch.
2. Make the smallest coherent change.
3. Run `make check` on a Linux development environment.
4. If kernel code changed, run `make module` against at least one supported
   header tree.
5. Update tests and documentation with the behavior change.
6. Open a pull request describing what was tested and what was not tested.

Do not report physical GPIO/I2C validation unless you performed it. Include the
board revision, OS/kernel, wiring, target part, measurement method, exact
commands, and sanitized logs in `docs/verification-log.md`.

## Kernel code expectations

- Preserve reverse-order cleanup for every newly acquired resource.
- Propagate the original kernel errno whenever possible.
- Never dereference a `__user` pointer; use the user-copy helpers and handle
  partial results.
- Keep shared mutable state under the device mutex or use a documented atomic.
- Use fixed-width, pointer-free UAPI fields and do not renumber released ioctls.
- Validate values before allocation, array access, bus traffic, or GPIO output.
- Keep hardware disabled by default and retain the `CAP_SYS_RAWIO` check.
- Avoid adding world-writable device permissions.

## Commit and pull-request style

Use imperative subjects such as `Handle partial user copies in write path`.
Keep refactors separate from behavior changes. A pull request should include:

- motivation and user-visible behavior;
- failure/cleanup analysis;
- commands and results for host tests and kernel compilation;
- hardware-validation status stated explicitly;
- UAPI compatibility impact, if any.

By contributing, you agree that your contribution is licensed under the MIT
License and may be used by the kernel module under its declared dual license.

