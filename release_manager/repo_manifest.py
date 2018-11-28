# Copyright (c) 2017, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""
Git repo manifet data storage classes.

This module defines CRepoManifestFile and CRepoManifestProject.
CRepoManifestFile is a storage class which holds data on a specific
manifest file found in the root of armmbed/mbl-manifest repository.
CRepoManifestProject is a storage class which holds data on a remote repository
to be fetched.
"""

import logging
from pprint import pformat

from git_utils import *
from main import program_name


logger = logging.getLogger(program_name)

MRR_MANIFEST_REMOTE_KEY = "github"


class CRepoManifestFile(object):
    """
    Manifest file related data storage class.

    This class stores information about manifest XML file in armmbed/mbl-
    manifest repository.
    """

    def __init__(
        self,
        path,
        filename,
        tree,
        root,
        default_rev,
        remote_key_to_remote_dict,
        repo_name_to_proj_dict,
    ):
        """Object initialization."""
        # destination path
        self.path = path

        # file name, without the suffix
        self.filename = filename

        # entire element hierarchy
        self.tree = tree

        # root ElementTree of file prase
        self.root = root

        # default revision (branch or tag) to checkout when not
        # specified in project
        self.default_rev = default_rev

        # dictionary : key is a remote name, value is a fetch prefix URL
        # This  dictionary holds all fetch URLs with a remote name as key
        self.remote_key_to_remote_dict = remote_key_to_remote_dict

        # dictionary : key is a repository short name, value is
        # This dictionary holds all CRepoManifestProject objects with
        # repository names as key
        self.repo_name_to_proj_dict = repo_name_to_proj_dict

        logger.debug(
            "Created new {} : {}".format(
                type(self).__name__, pformat(locals())
            )
        )


class CRepoManifestProject(object):
    """
    Manifest file project related data storage class.

    This class represents a google repo manifest file 'project' entry that
    needs to be cloned.

    Each CRepoManifestFile holds one or more CRepoManifestProject
    objects inside repo_name_to_proj_dict.
    """

    def __init__(
        self, full_name, prefix, short_name, remote_key, url, revision
    ):
        """Object initialization."""
        # full name such as 'armmbed/meta-mbl'
        self.full_name = full_name

        # prefix like 'armmbed'
        self.name_prefix = prefix

        # short name such as 'meta-mbl'
        self.short_name = short_name

        # key to CRepoManifestFile::remote_key_to_remote_dict
        self.remote_key = remote_key

        # repository URL
        self.url = url

        # revision to checkout, can be a branch, tag or commit hash
        # (the last 2 are experimental)
        self.revision = revision

        # place holder for CGitClonedRepository object
        self.cloned_repo = None

        # An ARM MRR must have project with :
        # remote -> MRR_MANIFEST_REMOTE_KEY = "github"
        # prefix -> ARM_MRR_REPO_NAME_PREFIX = "armmbed"
        if (self.name_prefix == ARM_MRR_REPO_NAME_PREFIX) and (
            self.remote_key == MRR_MANIFEST_REMOTE_KEY
        ):
            self.is_arm_mrr = True
        else:
            self.is_arm_mrr = False

        logger.debug(
            "Created new {} : {}".format(
                type(self).__name__, pformat(locals())
            )
        )
