#!/usr/bin/env python3

"""
Summary.

This file contains CRepoManifestFile class.
"""

#
# imports
#

import logging
from common import module_name
from pprint import pformat


#
#   Class CRepoManifestFile
#


class CRepoManifestFile(object):
    """
    class CRepoManifestFile.

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
        """..."""
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

        logger = logging.getLogger(module_name)
        logger.debug(
            "Created new {} : {}".format(
                type(self).__name__, pformat(locals())
            )
        )
