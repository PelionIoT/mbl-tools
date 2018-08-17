# What sanity checks are running?

For *shell scripts*, the following sanity checks will be running:
* tab_finder.py: custom script to find tabs on shell scripts
* [shellcheck] for shell scripts

For *python files*, the following sanity check will be running:
* [black] for python files
* [pycodestyle] (ex pep8) for python files
* [pep257] (for docstring) for python files

If any of the above checks returns a non-zero exit code, the whole sanity check script will fail.

# Requirements

The easiest way is to run it through docker, hence the only requirement is to have docker installed

If you choose to run it natively, then you need to install shellcheck, black, pycodestyle and pep257

Note: black requires Python 3.6.

# Usage

## Running with docker

The easiest way to run it is through docker

```
$ ./run-me.sh --workdir /path/to/your/project
```

This will create a docker container with all dependencies required and run the sanity checks.
Output will be printed on screen with the results.

## Running natively

You have the option to run it without docker but you need all the dependencies installed on your host.

```
$ ./sanity-check.sh --workdir /path/to/your/project
```

This will run the sanity checks on your project. Output will be printed on screen with the results.

## Skipping directories

You can disable sanity check for a specific sub-tree, placing an empty file named `.nosanitycheck` in the root of the sub-tree you want to skip. Example:

```
$ tree /path/to/workdir
/path/to/workdir           
├── dir1
│   ├── .nosanitycheck
│   └── file1                
└── dir2
    ├── subdir2
    │   ├── .nosanitycheck
    │   ├── file2
    │   └── subdir3
    │       └── file3
    ├── file4
    └── file5
```

If you run the sanity check on the above tree, the following directories are skipped:
* `dir1` and its contents (`file1`)
* the whole sub-tree with root `subdir2`: `file2` and `file3`

In the above case only `file4` and `file5` will be checked.


[shellcheck]: https://www.shellcheck.net/
[black]: https://black.readthedocs.io/en/stable/
[pycodestyle]: https://pypi.org/project/pycodestyle/
[pep257]: https://pypi.org/project/pep257/
