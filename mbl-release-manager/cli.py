#!/usr/bin/env python3

# Copyright (c) 2018, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""
Entry point.

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

The script supports:
* diagnostic mode requires user confirmation for each step
* Simulation mode - no real pushes are done to remote.
* temporary folder can be kept for analyzing
* At the end, a summary is printed to screen.
* Execution is accelerated at some parts by using thread pools.
"""

import release_manager


program_name = "mbl-release-manager"


def _main():

    with release_manager.ReleaseManager() as rm:

        # Parse JSON references input file
        new_revisions = rm.parse_input_file()

        # Validate JSON input file
        rm.validate_input_file(new_revisions)

        # Clone the manifest repository and parse its xml files into database
        rm.process_manifest_files()

        # Validate additional logical dependencies after parsing user
        # provided JSON file and mbl-manifest manifest files
        rm.validate_cross_dependencies()

        # prepare clone data to be an input for worker threads
        # cloning is done using a thread pool
        clone_data = rm.prepare_clone_data()

        # Create new revisions (as required by user) on remote repositories
        rm.create_new_revisions(clone_data)

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
