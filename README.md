# Embody File

[![PyPI](https://img.shields.io/pypi/v/embody-file.svg)][pypi_]
[![Status](https://img.shields.io/pypi/status/embody-file.svg)][status]
[![Python Version](https://img.shields.io/pypi/pyversions/embody-file)][python version]
[![License](https://img.shields.io/pypi/l/embody-file)][license]

[![Tests](https://github.com/aidee-health/embody-file/workflows/Tests/badge.svg)][tests]

[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)][pre-commit]
[![Black](https://img.shields.io/badge/code%20style-black-000000.svg)][black]

[pypi_]: https://pypi.org/project/embody-file/
[status]: https://pypi.org/project/embody-file/
[python version]: https://pypi.org/project/embody-file
[tests]: https://github.com/aidee-health/embody-file/actions?workflow=Tests
[pre-commit]: https://github.com/pre-commit/pre-commit
[black]: https://github.com/psf/black

This is a Python based implementation for parsing binary files from the Aidee EmBody device.

## Features

- Converts binary embody files to HDF, CSV, etc
- Integrates with [the EmBody Protocol Codec](https://github.com/aidee-health/embody-protocol-codec) project
- CLI (command line interface)
- Can be used as package in other projects
- Type safe code using [mypy](https://mypy.readthedocs.io/) for type checking

## Requirements

- Python 3.8-3.11

## Installation

You can install _Embody File_ via [pip]:

```console
$ pip install embody-file
```

## Usage

To use the command line, first install this library either globally or using venv:

```console
$ pip install embody-file
```

When this library has been installed, a new command is available, `embody-file` which can be used according to the examples below:

### Get help

To get an updated overview of all command line options:

```bash
embody-file --help
```

### Print version number

```bash
embody-file --version
```

### Convert binary embody file to HDF

To convert to a [HDF 5 (hierarcical data format)](https://en.wikipedia.org/wiki/Hierarchical_Data_Format) format, run the following:

```bash
embody-file testfiles/v5_0_0_test_file.log --output-format HDF
```

The file will be named the same as the input file, with the `.hdf` extension at the end of the file name.

### Convert binary embody file to CSV

To convert to CSV format, run the following:

```bash
embody-file testfiles/v5_0_0_test_file.log --output-format CSV
```

The file will be named the same as the input file, with the `.csv` extension at the end of the file name.

### Print statistics for binary embody file

To print stats without conversion:

```bash
embody-file testfiles/v5_0_0_test_file.log --print-stats
```

### Plot binary file in graph

To show an ECG/PPG plot graph:

```bash
embody-file testfiles/v5_0_0_test_file.log --plot
```

## Contributing

Contributions are very welcome.
To learn more, see the [Contributor Guide].

## Issues

If you encounter any problems,
please [file an issue] along with a detailed description.

[file an issue]: https://github.com/aidee-health/embody-file/issues
[pip]: https://pip.pypa.io/

<!-- github-only -->

[license]: https://github.com/aidee-health/embody-file/blob/main/LICENSE
[contributor guide]: https://github.com/aidee-health/embody-file/blob/main/CONTRIBUTING.md
[command-line reference]: https://embody-file.readthedocs.io/en/latest/usage.html
