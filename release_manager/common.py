#!/usr/bin/env python3


# Copyright (c) 2017, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""
Summary.

This file holds common definitions to import, and helper common functions
gathered under static class SCommonFuncs.
"""

#
# imports
#

import git
import os

#
# common constants
#

module_name = "release_manager"
__version__ = "1.0.0"

REF_BRANCH_PREFIX = "refs/heads/"
REF_TAG_PREFIX = "refs/tags/"
REF_PREFIX = "refs/"
ARM_MRR_REPO_NAME_PREFIX = "armmbed"
HASH_FIXED_LEN = 40

#
#   Class SCommonFuncs
#


class SCommonFuncs:
    """
    static class SCommonFuncs.

    This class group together short helper functions that are used (or might
    be used) by multiple objects.
    """

    # static vars
    logger = None

    @staticmethod
    def build_url_from_repo_name(remote_prefix, repo_name):
        """..."""
        return "{}:/{}.git".format(remote_prefix, repo_name)

    @staticmethod
    def build_url_from_base_repo_name(remote_prefix, prefix, base_name):
        """..."""
        return SCommonFuncs.build_url_from_repo_name(
            remote_prefix, prefix + "/" + base_name
        )

    @staticmethod
    def list_remote_references(url):
        """Return a dictionary of references for a git remote URL."""
        remote_refs_dict = {}
        g = git.cmd.Git()
        for ref in g.ls_remote(url).split("\n"):
            v, k = ref.split("\t")
            remote_refs_dict[k] = v
        return remote_refs_dict

    @staticmethod
    def is_branch_exist_in_remote_repo(repo_url, branch_name, is_base_name):
        """
        summary.

        Returns True if 'branch_name' exist in remote repository in URL
        'repo_url.
        """
        refs = SCommonFuncs.list_remote_references(repo_url)
        if is_base_name:
            if "refs/heads/" + branch_name in refs:
                return True
        if branch_name in refs:
            return True
        return False

    @staticmethod
    def is_tag_exist_in_remote_repo(repo_url, tag_name, is_base_name):
        """
        summary.

        Returns True if 'branch_name' exist in remote repository in URL
        'repo_url'.
        """
        refs = SCommonFuncs.list_remote_references(repo_url)
        if is_base_name:
            if "refs/tags/" + tag_name in refs:
                return True
        if tag_name in refs:
            return True
        return False

    @staticmethod
    def get_file_name_from_path(path, no_suffix_flag):
        """..."""
        ret = os.path.basename(path)
        if no_suffix_flag:
            tup = os.path.splitext(ret)
            ret = tup[0]
        return ret

    @staticmethod
    def get_base_rev_name(full_rev_name):
        """..."""
        return full_rev_name.rsplit("/", 1)[1]

    @staticmethod
    def is_valid_revision(rev):
        """..."""
        if (
            not SCommonFuncs.is_valid_git_commit_hash(rev)
            and not SCommonFuncs.is_valid_git_branch_name(rev)
            and not SCommonFuncs.is_valid_git_tag_name(rev)
        ):
            return False
        return True

    @staticmethod
    def is_valid_git_ref_name(ref):
        """..."""
        if not ref.startswith(REF_PREFIX):
            return False
        g = git.cmd.Git()
        try:
            if g.check_ref_format("--normalize", ref) != ref:
                raise ValueError
        except git.GitCommandError:
            return False
        except ValueError:
            return False
        return True

    # A valid commit hash must be 40 characters long and hexadecimal
    @staticmethod
    def is_valid_git_commit_hash(commit_hash):
        """..."""
        if len(commit_hash) != HASH_FIXED_LEN:
            return False
        try:
            int(commit_hash, 16)
        except ValueError:
            return False
        return True

    @staticmethod
    def is_valid_git_branch_short_name(branch_name):
        """..."""
        g = git.cmd.Git()
        try:
            if g.check_ref_format("--branch", branch_name) != branch_name:
                raise ValueError
        except git.GitCommandError:
            return False
        except ValueError:
            return False
        return True

    @staticmethod
    def is_valid_git_branch_name(branch_name):
        """Return True is 'branch_name' is a valid git branch name."""
        if not branch_name.startswith(REF_BRANCH_PREFIX):
            return False
        return SCommonFuncs.is_valid_git_ref_name(branch_name)

    @staticmethod
    def is_valid_git_tag_name(tag_name):
        """..."""
        if not tag_name.startswith(REF_TAG_PREFIX):
            return False
        return SCommonFuncs.is_valid_git_ref_name(tag_name)
