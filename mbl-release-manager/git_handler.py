# Copyright (c) 2018, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""
This module deals with the Git local and remote repositories.

Defines GitClonedRepository class which holds cloned repository information,
and also operations on that repository.
Also holds Git Common definitions and helper functions.

"""

import os

import git
import logging
from pprint import pformat

import cli


REF_BRANCH_PREFIX = "refs/heads/"
REF_TAG_PREFIX = "refs/tags/"
REF_PREFIX = "refs/"
HASH_FIXED_LEN = 40


def validate_remote_repositories_state_helper(url, new_rev):
    """Check that new rev does not exist on remote."""
    if new_rev.startswith(REF_BRANCH_PREFIX):
        return does_branch_exist_in_remote_repo(url, new_rev, False)
    if new_rev.startswith(REF_TAG_PREFIX):
        return does_tag_exist_in_remote_repo(url, new_rev, False)

    return True


def build_url_from_repo_name(remote_prefix, repo_name):
    """
    Build a remote URL from remote prefix and remote name.

    Return a git remote URL from a remote prefix and a repository
    short name.
    """
    return "{}:/{}.git".format(remote_prefix, repo_name)


def build_url_from_base_repo_name(remote_prefix, prefix, base_name):
    """Build remote URL from given tokens according to template."""
    return build_url_from_repo_name(
        remote_prefix, "{}/{}".format(prefix, base_name)
    )


def list_remote_references(url):
    """
    Return a dictionary 'remote_refs' of references for a git remote URL.

    The dictionary is composed of :
    key - a Git reference available in a remote repository
    value -  associated commit ID (SHA-1) hash
    """
    remote_refs = {}
    git_obj = git.cmd.Git()
    for ref in git_obj.ls_remote(url).split("\n"):
        commit_hash, ref_path = ref.split("\t")
        remote_refs[ref_path] = commit_hash
    return remote_refs


def does_branch_exist_in_remote_repo(repo_url, branch_name, is_base_name):
    """
    Check if branch exist on remote repository.

    Returns True if 'branch_name' exist in remote repository in URL
    'repo_url.
    """
    refs = list_remote_references(repo_url)
    if all([is_base_name, (REF_BRANCH_PREFIX + branch_name) in refs]):
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
        if (REF_TAG_PREFIX + tag_name) in refs:
            return True
    if tag_name in refs:
        return True
    return False


def get_file_name_from_path(path, add_suffix_flag):
    """Get a short file name from path, or a full file_name with suffix."""
    file_name = os.path.basename(path)
    if not add_suffix_flag:
        path_tokens = os.path.splitext(file_name)
        file_name = path_tokens[0]
    return file_name


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


class GitClonedRepository:
    """
    This storage class defines a Git cloned repository.

    All cloned repositories are
    kept under RepoManifestProject cloned_repo or
    ReleaseManager::external_repo_name_to_cloned_repo.
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
        self.logger = logging.getLogger(cli.program_name)

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
            self.handle = self.clone_repo(self.checkout_rev)
        else:

            # try to clone as a short name branch
            try:
                self.handle = self.clone_repo(
                    (REF_BRANCH_PREFIX + self.checkout_rev)
                )
            except ValueError:
                # try to clone as a short name tag
                self.handle = self.clone_repo(
                    (REF_TAG_PREFIX + self.checkout_rev)
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

    def clone_repo(self, checkout_rev_name="refs/heads/master"):
        """
        Clone a new repository from URL.

        Clone a repository from 'url' into path 'dest_full_path' and
        checkout revision 'checkout_rev_name' Return a cloned repository
        object.
        """
        url = self.url
        dest_path = self.clone_dest_path
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
                "Invalid checkout_rev_name {} to checkout "
                "after cloning!".format(checkout_rev_name)
            )

        # create the destination directory if it does not exist
        if not os.path.exists(dest_path):
            self.logger.info("Creating new folder {}".format(dest_path))
            os.makedirs(dest_path)

        # now clone
        if is_commit_hash:
            self.logger.info(
                "Cloning repository {} to {} and checking out "
                "commit hash {}".format(url, dest_path, checkout_revision)
            )
            cloned_repo = git.Repo.clone_from(url, dest_path)
            cloned_repo.git.checkout(checkout_revision)
        else:
            cloned_repo = git.Repo.clone_from(
                url, dest_path, branch=checkout_revision
            )
            self.logger.info(
                "Cloning repository {} to {} and checking out "
                "branch {}".format(url, dest_path, checkout_revision)
            )

        assert cloned_repo.__class__ is git.Repo
        return cloned_repo
