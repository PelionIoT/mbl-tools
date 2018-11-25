#!/usr/bin/env python3

"""
Summary.

This file holds CGitClonedRepository class
"""

#
# imports
#

from common import *
from git import Repo
import logging
from pprint import pformat

#
#   Class CGitClonedRepository
#


class CGitClonedRepository(object):
    """
    class CGitClonedRepository.

    This class represents a cloned repository.
    All cloned repositories are
    kept under CRepoManifestProject cloned_repo or
    CReleaseManager::additional_repo_name_to_cloned_repo_dict.
    """

    def __init__(
        self, remote, name_prefix, short_name, clone_base_path, checkout_rev
    ):
        """init."""
        # name, name prefix , full name
        self.short_name = short_name
        self.name_prefix = name_prefix
        self.full_name = name_prefix + "/" + short_name

        # remote
        self.remote = remote

        # checkout branch name
        self.checkout_rev = checkout_rev

        # full clone destination path
        self.clone_dest_path = os.path.join(clone_base_path, self.short_name)

        # repo url
        self.url = SCommonFuncs.build_url_from_base_repo_name(
            remote, name_prefix, short_name
        )

        # clone and get git.Repo object
        if (
            self.checkout_rev.startswith(REF_BRANCH_PREFIX)
            or self.checkout_rev.startswith(REF_TAG_PREFIX)
            or len(self.checkout_rev) == HASH_FIXED_LEN
        ):

            self.handle = self.clone_repo(
                self.clone_dest_path, self.url, self.checkout_rev
            )
        else:

            # try to clone as branch
            try:
                self.handle = self.clone_repo(
                    self.clone_dest_path,
                    self.url,
                    REF_BRANCH_PREFIX + self.checkout_rev,
                )

            except ValueError:
                # try to clone as tag
                self.handle = self.clone_repo(
                    self.clone_dest_path, self.url, self.checkout_rev
                )
        logger = logging.getLogger(module_name)
        logger.debug(
            "Created new {} : {}".format(
                type(self).__name__, pformat(locals())
            )
        )
        logger.info(
            "{} Cloned from remote {} to folder {}".format(
                self.full_name, self.url, self.clone_dest_path
            )
        )

    def clone_repo(
        self, dest_full_path, url, checkout_rev_name="refs/heads/master"
    ):
        """
        clone_repo.

        clone a repository from 'url' into path 'dest_full_path' and
        checkout revision 'checkout_rev_name' returns a cloned repository
        object.
        """
        is_commit_hash = False
        if SCommonFuncs.is_valid_git_branch_name(
            checkout_rev_name
        ) and SCommonFuncs.is_branch_exist_in_remote_repo(
            url, checkout_rev_name, False
        ):
            co_branch = SCommonFuncs.get_base_rev_name(checkout_rev_name)
        elif SCommonFuncs.is_valid_git_tag_name(
            checkout_rev_name
        ) and SCommonFuncs.is_tag_exist_in_remote_repo(
            url, checkout_rev_name, False
        ):
            co_branch = SCommonFuncs.get_base_rev_name(checkout_rev_name)
        elif SCommonFuncs.is_valid_git_commit_hash(checkout_rev_name):
            co_branch = checkout_rev_name
            is_commit_hash = True
        else:
            raise ValueError(
                "Invalid checkout_rev_name %s to checkout after cloning!"
                % checkout_rev_name
            )

        # create folder if not exist
        if not os.path.exists(dest_full_path):
            SCommonFuncs.logger.info("Creating new folder %s" % dest_full_path)
            os.makedirs(dest_full_path)

        # now clone
        if is_commit_hash:
            SCommonFuncs.logger.info(
                "Cloning repository {} to {} and checking out "
                "commit hash {}".format(url, dest_full_path, co_branch)
            )
            cloned_repo = Repo.clone_from(url, dest_full_path)
            cloned_repo.git.checkout(co_branch)
        else:
            cloned_repo = Repo.clone_from(
                url, dest_full_path, branch=co_branch
            )
            SCommonFuncs.logger.info(
                "Cloning repository {} to {} and checking out "
                "branch {}".format(url, dest_full_path, co_branch)
            )

        assert cloned_repo.__class__ is Repo
        return cloned_repo
