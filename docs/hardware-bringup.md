# Hardware bring-up checklist

This checklist separates implemented code from observed hardware evidence. Do
not mark a step complete until it was performed on the named test system.

## Before power or module load

- [ ] Record Raspberry Pi model/revision, OS image, `uname -a`, and commit SHA.
- [ ] Review the board pinout and target device datasheet.
- [ ] Confirm 3.3 V logic compatibility and a shared ground.
- [ ] Confirm GPIO global numbering for this kernel; do not assume BCM or header
      numbering maps directly.
- [ ] Confirm no Device Tree overlay or driver already owns the GPIO.
- [ ] Run `i2cdetect -l` and identify the intended adapter.
- [ ] Confirm the 7-bit I2C address and that no bound kernel driver owns it.
- [ ] Verify pull-ups, supply, and safe GPIO initial/active polarity.
- [ ] Arrange a meter, oscilloscope, or logic analyzer; software output alone is
      not electrical validation.

## Memory-only baseline

```bash
make all
sudo bash scripts/load.sh
bash scripts/smoke-test.sh
./user/simple-char-cli stats
sudo bash scripts/unload.sh
sudo bash scripts/repeat-load-unload.sh 25
```

Save stdout, stderr, relevant `dmesg`, and the final absence of
`/sys/class/simple_char` and `/dev/simple_char`.

## GPIO validation

1. Keep the external load disconnected for the first polarity check.
2. Load with the verified global number and active-low option, if required.
3. Measure the initial logical-zero level.
4. Issue `gpio 1`, then `gpio 0`; record measured levels and timestamps.
5. Unload and confirm the line returns to logical zero before release.
6. Repeat enough cycles to expose ownership/cleanup issues.

Abort on unexpected voltage, heat, ownership errors, or mismatched numbering.

## I2C validation

1. Read the target datasheet's register semantics before choosing a register.
2. Load with the verified adapter and 7-bit address.
3. Write only to a known-safe scratch/configuration register.
4. Observe the transaction with an analyzer or independently read it through an
   appropriate device-aware tool.
5. Disconnect the target or use a known unused address and confirm the adapter's
   NACK errno reaches the client.
6. Unload, then confirm the address can be acquired again.

## Evidence minimum

For each result record the date, operator, commit, kernel, compiler, exact
command, exit status, relevant log excerpt, physical setup, expected result, and
observed result. Use `docs/verification-log.md`; remove secrets and unrelated
machine identifiers before publishing.

