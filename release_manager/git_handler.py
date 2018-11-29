# Copyright (c) 2017, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""
This module deals with the Git local and remote repositories.

Defines CGitClonedRepository class which holds cloned repository information,
and also operations on that repository.
Also holds Git Common definitions and helper functions.

"""

import os

import git
from git import Repo
import logging
from pprint import pformat

from main import program_name


REF_BRANCH_PREFIX = "refs/heads/"
REF_TAG_PREFIX = "refs/tags/"
REF_PREFIX = "refs/"
HASH_FIXED_LEN = 40


def build_url_from_repo_name(remote_prefix, repo_name):
    """
    Build a remote URL from remote prefix and remote name.

    Return a git remote URL from a remote prefix and a repository
    short name.
    """
    return "{}:/{}.git".format(remote_prefix, repo_name)


def build_url_from_base_repo_name(remote_prefix, prefix, base_name):
    """Build remote URL from given tokens according to template."""
    return build_url_from_repo_name(remote_prefix, prefix + "/" + base_name)


def list_remote_references(url):
    """Return a dictionary of references for a git remote URL."""
    remote_refs_dict = {}
    git_obj = git.cmd.Git()
    for ref in git_obj.ls_remote(url).split("\n"):
        value, key = ref.split("\t")
        remote_refs_dict[key] = value
    return remote_refs_dict


def does_branch_exist_in_remote_repo(repo_url, branch_name, is_base_name):
    """
    Check if branch exist on remote repository.

    Returns True if 'branch_name' exist in remote repository in URL
    'repo_url.
    """
    refs = list_remote_references(repo_url)
    if all([is_base_name, ("refs/heads/" + branch_name) in refs]):
        return True
    if branch_name in refs:
        return True
    return False


def does_tag_exist_in_remote_repo(repo_url, tag_name, is_base_name):
    """
    Check if tag exist on remote repository.

    Returns True if 'branch_name' exist in remote repository in URL
    'repo_url'.
    """
    refs = list_remote_references(repo_url)
    if is_base_name:
        if ("refs/tags/" + tag_name) in refs:
            return True
    if tag_name in refs:
        return True
    return False


def get_file_name_from_path(path, add_suffix_flag):
    """Get a short file name from path, or a full filename with suffix."""
    filename = os.path.basename(path)
    if not add_suffix_flag:
        path_tokens = os.path.splitext(filename)
        filename = path_tokens[0]
    return filename


def get_base_rev_name(full_rev_name):
    """Get the short base revisoion name of a branch or a tag."""
    return full_rev_name.rsplit("/", 1)[1]


def is_valid_revision(rev):
    """Return True of a revision is a commit hash, tag or branch."""
    return any(
        [
            is_valid_git_commit_hash(rev),
            is_valid_git_branch_name(rev),
            is_valid_git_tag_name(rev),
        ]
    )


def is_valid_git_ref_name(ref):
    """Return true is a Git reference (branch/tag) is valid."""
    if not ref.startswith(REF_PREFIX):
        return False
    git_cmd = git.cmd.Git()
    try:
        if git_cmd.check_ref_format("--normalize", ref) != ref:
            raise ValueError
    except git.GitCommandError:
        return False
    except ValueError:
        return False
    return True


def is_valid_git_commit_hash(commit_hash):
    """
    Check if a commit hash is valid.

    Return true if commit hash is valid - length of HASH_FIXED_LEN and
    only hexadecimal characters.
    """
    if len(commit_hash) != HASH_FIXED_LEN:
        return False
    try:
        int(commit_hash, 16)
    except ValueError:
        return False
    return True


def is_valid_git_branch_short_name(branch_name):
    """Return True if a short name branch is valid."""
    git_cmd = git.cmd.Git()
    try:
        if git_cmd.check_ref_format("--branch", branch_name) != branch_name:
            raise ValueError
    except git.GitCommandError:
        return False
    except ValueError:
        return False
    return True


def is_valid_git_branch_name(branch_name):
    """Return True is 'branch_name' is a valid git branch name."""
    if not branch_name.startswith(REF_BRANCH_PREFIX):
        return False
    return is_valid_git_ref_name(branch_name)


def is_valid_git_tag_name(tag_name):
    """Return true of short tag name is valid."""
    if not tag_name.startswith(REF_TAG_PREFIX):
        return False
    return is_valid_git_ref_name(tag_name)


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
        Tries to clone first in the form refs/heads/branch_name or
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
                "Invalid checkout_rev_name {} to checkout after cloning!"
                % checkout_rev_name
            )

        # create the destination directory if it does not exist
        if not os.path.exists(dest_full_path):
            self.logger.info("Creating new folder {}".format(dest_full_path))
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
