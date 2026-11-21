# Contributing

The installer runs on a Synology NAS as root and changes package compatibility
limits, package versions, and installed packages. Run development checks on your
workstation. Use a disposable DSM installation or a NAS with a current backup for
installation testing.

## Local checks

Install Python 3, Bash, Git, jq, and pre-commit on your workstation, then run:

```sh
pre-commit install
pre-commit run --all-files
```

The pinned hooks check whitespace, YAML and JSON, merge conflicts, private keys,
large added files, shell warnings, Bash syntax, and installer regression tests.
The first run downloads hook environments. No hook runs the installer against
DSM. Workflow files and ownership rules are excluded from hook changes.

To run the behavior tests separately:

```sh
python3 -m unittest discover -s tests -v
```

Tests cover argument parsing, complete simulated installation flows, package
downloads, selected-volume API contracts, and settings inspection. The optional
subtitle adapter has executable PHP tests; install PHP on your workstation to
run those tests too. They use temporary files and mocked network commands and
do not establish DSM compatibility. See the [subtitle development notes](docs/subtitle-compatibility.md)
for runtime requirements and additional validation.

## Device verification

Before releasing changes to installation behavior, record the NAS model, CPU
platform, complete DSM version, selected packages, and results of installation,
restart, and playback. Check both a fresh installation and a rerun after a DSM
update. Test every supported architecture affected by a binary change.

Keep the remaining device checks in [compatibility notes](docs/compatibility.md)
open until those results exist. Do not substitute a package metadata version
change for a playback or codec test.

Follow the repo's guidelines. Do not change workflow files or ownership rules.
Keep private addresses, credentials, and personal contact details out of changes.
Sign off commits with `git commit -s` using an approved public commit identity.
