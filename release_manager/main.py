#!/usr/bin/env python3

# Copyright (c) 2017, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""
Summary.

This script can be called from command line, or used from the mbl-tools.
In short:
* It receives a json formatted file with entries of 2 types :
1) New branch/tag to be created and pushed to remote for Arm MRRs or Arm
    external repositories
2) New branch/tag/commit hash to replace in manifest files for non-Arm MRRs.

* Clones all repositories of type 1), create branch/tag and push to remote
* Update armmbed/mbl-manifest repository manifest XML files accordingly,
    commit and push to remote
* Update armmbed/meta-mbl/conf/dist/mbl-linked-repositories.conf accordingly,
    commit and push to remote.

The script supports :
* diagnostic mode requires user confirmation for each step
* Simulation mode - no real pushes are done to remote.
* temporary folder can be kept for analyzing
* At the end, a summary is printed to screen.
* Execution is accelerated at some parts by using thread pools.

Prerequisite:
Install python packages 'gitpython' and 'in_place':
$ pip3 install gitpython in_place

# SPDX-License-Identifier: Apache-2.0
"""


#
# imports
#

from release_manager import *


def _main():

    with CReleaseManager() as rm:

        # Parse JSON references input file
        rm.parse_and_validate_input_file()

        # Clone the manifest repository and parse its xml files into database
        rm.process_manifest_files()

        # Some more things to validate between input and manifest files file
        # after parsing both files
        rm.validate_cross_dependencies()

        # Update new_revision for all manifest files projects and create
        # reference (where needed on
        # remote Git repositories)
        rm.clone_and_create_new_revisions()

        # update all files MBL_LINKED_REPOSITORIES_REPO_PATH in repositories
        # MBL_LINKED_REPOSITORIES_REPO_NAME
        rm.update_mbl_linked_repositories_conf()

        # Commit MBL_LINKED_REPOSITORIES_REPO_NAME and MBL_MANIFEST_REPO_NAME
        # and push to remote
        rm.mbl_manifest_repo_push()

        # print summary
        rm.print_summary()

        # mark success
        rm.completed = True


if __name__ == "__main__":
    sys.exit(_main())
