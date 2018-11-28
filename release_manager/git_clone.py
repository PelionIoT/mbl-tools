# Copyright (c) 2017, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""
This module deals with the Git local and remote repositories.

Defines CGitClonedRepository class which holds cloned repository information,
and also operations on that repository.
"""


from git import Repo
import logging
from pprint import pformat

from git_utils import *
from main import program_name


class CGitClonedRepository(object):
    """
    This storage class defines a Git cloned repository.

    All cloned repositories are
    kept under CRepoManifestProject cloned_repo or
    CReleaseManager::external_repo_name_to_cloned_repo_dict.
    """

    def __init__(
        self, remote, name_prefix, short_name, clone_base_path, checkout_rev
    ):
        """Object initialization."""
        # repository short name (for example meta-mbl).
        self.short_name = short_name

        # repository prefix (for example armmbed).
        self.name_prefix = name_prefix

        # repository full name (for example armmbed/meta-mbl).
        self.full_name = name_prefix + "/" + short_name

        # get logger
        self.logger = logging.getLogger(program_name)

        # remote URL prefix
        self.remote_url_prefix = remote

        # checkout branch name
        self.checkout_rev = checkout_rev

        self.clone_dest_path = os.path.join(clone_base_path, self.short_name)

        self.url = build_url_from_base_repo_name(
            remote, name_prefix, short_name
        )

        """
        Clone and get git.Repo object.
        Trys to clone first in the form refs/heads/branch_name or 
        refs/tags/tag_name. If the user gave just tag_name or branch_name,
        try to clone them in the else block.
        """
        if is_valid_revision(self.checkout_rev):
            self.handle = self.clone_repo(
                self.clone_dest_path, self.url, self.checkout_rev
            )
        else:

            # try to clone as a short name branch
            try:
                self.handle = self.clone_repo(
                    self.clone_dest_path,
                    self.url,
                    (REF_BRANCH_PREFIX + self.checkout_rev),
                )

            except ValueError:
                # try to clone as a short name tag
                self.handle = self.clone_repo(
                    self.clone_dest_path, self.url, self.checkout_rev
                )
        self.logger.debug(
            "Created new {} : {}".format(
                type(self).__name__, pformat(locals())
            )
        )
        self.logger.info(
            "{} Cloned from remote {} to folder {}".format(
                self.full_name, self.url, self.clone_dest_path
            )
        )

    def clone_repo(
        self, dest_full_path, url, checkout_rev_name="refs/heads/master"
    ):
        """
        Clone a new repository from URL.

        Clone a repository from 'url' into path 'dest_full_path' and
        checkout revision 'checkout_rev_name' Return a cloned repository
        object.
        """
        is_commit_hash = False
        if is_valid_git_branch_name(
            checkout_rev_name
        ) and does_branch_exist_in_remote_repo(url, checkout_rev_name, False):
            checkout_revision = get_base_rev_name(checkout_rev_name)
        elif is_valid_git_tag_name(
            checkout_rev_name
        ) and does_tag_exist_in_remote_repo(url, checkout_rev_name, False):
            checkout_revision = get_base_rev_name(checkout_rev_name)
        elif is_valid_git_commit_hash(checkout_rev_name):
            checkout_revision = checkout_rev_name
            is_commit_hash = True
        else:
            raise ValueError(
                "Invalid checkout_rev_name %s to checkout after cloning!"
                % checkout_rev_name
            )

        # create the destination directory if it does not exist
        if not os.path.exists(dest_full_path):
            self.logger.info("Creating new folder %s" % dest_full_path)
            os.makedirs(dest_full_path)

        # now clone
        if is_commit_hash:
            self.logger.info(
                "Cloning repository {} to {} and checking out "
                "commit hash {}".format(url, dest_full_path, checkout_revision)
            )
            cloned_repo = Repo.clone_from(url, dest_full_path)
            cloned_repo.git.checkout(checkout_revision)
        else:
            cloned_repo = Repo.clone_from(
                url, dest_full_path, branch=checkout_revision
            )
            self.logger.info(
                "Cloning repository {} to {} and checking out "
                "branch {}".format(url, dest_full_path, checkout_revision)
            )

        assert cloned_repo.__class__ is Repo
        return cloned_repo
