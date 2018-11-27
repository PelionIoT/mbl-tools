#!/usr/bin/env python3

"""
Summary.

THis file contains CRepoManifestProject class.
"""

#
# imports
#

import logging
from pprint import pformat

from common import *

#
# constants
#

MRR_MANIFEST_REMOTE_KEY = "github"

#
#   Class CRepoManifestProject
#


class CRepoManifestProject(object):
    """
    class CRepoManifestProject.

    This class represents a google repo manifest file 'project' entry that
    needs to be cloned.

    Each CRepoManifestFile holds one or more CRepoManifestProject
    objects inside repo_name_to_proj_dict.
    """

    def __init__(
        self, full_name, prefix, short_name, remote_key, url, revision
    ):
        """..."""
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
            self.isArmMRR = True
        else:
            self.isArmMRR = False

        logger = logging.getLogger(module_name)
        logger.debug(
            "Created new {} : {}".format(
                type(self).__name__, pformat(locals())
            )
        )
