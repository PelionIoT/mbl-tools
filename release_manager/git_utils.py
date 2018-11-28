# Copyright (c) 2017, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""
Common definitions and global functions.

This file holds common definitions to import, and helper common functions
gathered under static class
"""

import os

import git


REF_BRANCH_PREFIX = "refs/heads/"
REF_TAG_PREFIX = "refs/tags/"
REF_PREFIX = "refs/"
ARM_MRR_REPO_NAME_PREFIX = "armmbed"
HASH_FIXED_LEN = 40


def build_url_from_repo_name(remote_prefix, repo_name):
    """
    build a remote URL from remote prefix and remote name.

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
    ret = os.path.basename(path)
    if not add_suffix_flag:
        tup = os.path.splitext(ret)
        ret = tup[0]
    return ret


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
    g = git.cmd.Git()
    try:
        if g.check_ref_format("--normalize", ref) != ref:
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
    g = git.cmd.Git()
    try:
        if g.check_ref_format("--branch", branch_name) != branch_name:
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
