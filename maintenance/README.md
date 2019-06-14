## Purpose

This directory contains the tools necessary to:

* Create release branches
* Tag a set of release branches
* Maintain master by cherry-picking from the dev branch

It does this by containing two repo manifests of all the repositories to be maintained in MBL and using the repo tool to check them out and act on them:

* `default.xml` - for the master maintenance (only on master)
* `release.xml` - for the development branch or release branches

It also contains some helper scripts in `scripts`.

Note: Some of the repositories may not be public at this time, as this process is for internal usage at this time.

## Directions

Maintenance on master:

```
mkdir my-workdir ; cd my-workdir
git clone git@github.com:ARMmbed/mbl-tools -b master
mbl-tools/maintenance/scripts/git-sync-start.bash my-maintenance
```

Release on default dev branch:
```
mkdir my-workdir ; cd my-workdir
git clone git@github.com:ARMmbed/mbl-tools
mbl-tools/maintenance/scripts/git-sync-start.bash --release my-release
```

After running these commands, follow the help printed from the `git-sync-start.bash` script.
