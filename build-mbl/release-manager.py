#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

#
# imports
#

import in_place
import time
import string
import random
import shutil
import re
import ntpath
import concurrent.futures
import tempfile
import argparse
import logging
import json
import sys
import git
import glob
import os
from git import Repo
from shutil import copyfile
from pprint import pformat
import xml.etree.ElementTree as ElementTree


"""
This script can be called from command line, or used from the mbl-tools.
In short:
* It receives a json formatted file with entries of 2 types :
1) New branch/tag to be created and pushed to remote for Arm MRRs or Arm
    additional repositories
2) New branch/tag/commit hash to replace in manifest files for non-Arm MRRs.

* Clones all repositories of type 1), create branch/tag and push to remote
* Update armmbed/mbl-manifest repository manifest XML files accordingly,
    commit and push to remote
* Update armmbed/meta-mbl/conf/dist/mbl-linked-repositories.conf accordingly,
    commit and push to remote.

The script supports :
* diagnostic mode requires user confirmation for each step
* Simulation mode - no real pushes are done to remote.
* temporary folder can be kept for analyzing
* At the end, a summary is printed to screen.
* Execution is accelerated at some parts by using thread pools.

Prerequisite:
Install python packages 'gitpython' and 'in_place':
$ pip3 install gitpython in_place

"""

module_name = "release_manager"
__version__ = "1.0.0"


#
# constants
#

COMMON_SD_KEY_NAME = "_common_"
ADDITIONAL_SD_KEY_NAME = "_additional_"
MAX_TMO_SEC = 120
MRR_MANIFEST_REMOTE_KEY = "github"
REF_PREFIX = "refs/"
REF_BRANCH_PREFIX = "refs/heads/"
REF_TAG_PREFIX = "refs/tags/"
HASH_FIXED_LEN = 40
INPUT_FILE_NAME = "update.json"
FILE_BACKUP_SUFFIX = "~"

#
# remote URL constants
#

ARM_MRR_REMOTE = "ssh://git@github.com"
ARM_MRR_URL_PATTERN = "ssh://git@github.com:/{}/{}.git"
ARM_MRR_REPO_NAME_PREFIX = "armmbed"
MBL_MANIFEST_REPO_SHORT_NAME = "mbl-manifest"
# armmbed/mbl-manifest
MBL_MANIFEST_REPO_NAME = "{}/{}".format(
    ARM_MRR_REPO_NAME_PREFIX, MBL_MANIFEST_REPO_SHORT_NAME)
GIT_REMOTE_NAME = "origin"

#
# mbl-linked-repositories.conf update constants
#

MBL_LINKED_REPOSITORIES_REPO_NAME = "armmbed/meta-mbl"
MBL_LINKED_REPOSITORIES_REPO_PATH = "conf/distro/mbl-linked-repositories.conf"

#
# logging
#

LOGGING_REGULAR_FORMAT = "\n%(asctime)s - %(name)s - " \
                         "{%(funcName)s:%(lineno)d} - " \
                         "%(levelname)s \n%(message)s"
LOGGING_SUMMARY_FORMAT = "%(message)s"
logger = logging.getLogger(module_name)
# list of strings to be printed at the script end, as a summary
summary_log_list = []
SUMMARY_H_PUSH = "PUSH: "
SUMMARY_H_MODIFY_FILE = "MODIFY FILE: "
SUMMARY_H_BKP = "CREATE BACKUP FILE: "
SUMMARY_H_BRANCH = "CREATE BRANCH: "
SUMMARY_H_TAG = "CREATE TAG: "
#
#   Class SGlobalFuncs
#


class SGlobalFuncs:
    """This class group together short helper functions that are used
    (or might be used) by multiple objects"""

    @staticmethod
    def build_url_from_repo_name(remote_prefix, repo_name):
        """"""
        return "{}:/{}.git".format(remote_prefix, repo_name)

    @staticmethod
    def build_url_from_base_repo_name(remote_prefix, prefix, base_name):
        """"""
        return SGlobalFuncs.build_url_from_repo_name(remote_prefix, prefix +
                                                     "/" + base_name)

    @staticmethod
    def lsremote(url):
        """Returns a dictionary of references for a git remote URL"""
        remote_refs_dict = {}
        g = git.cmd.Git()
        for ref in g.ls_remote(url).split('\n'):
            v, k = ref.split('\t')
            remote_refs_dict[k] = v
        return remote_refs_dict

    @staticmethod
    def is_branch_exist_in_remote_repo(repo_url, branch_name, is_base_name):
        """Returns True if 'branch_name' exist in remote repository
        in URL 'repo_url"""
        refs = SGlobalFuncs.lsremote(repo_url)
        if is_base_name:
            if 'refs/heads/' + branch_name in refs:
                return True
        if branch_name in refs:
            return True
        return False

    @staticmethod
    def is_tag_exist_in_remote_repo(repo_url, tag_name, is_base_name):
        """Returns True if 'branch_name' exist in remote repository
        in URL 'repo_url'"""
        refs = SGlobalFuncs.lsremote(repo_url)
        if is_base_name:
            if 'refs/tags/' + tag_name in refs:
                return True
        if tag_name in refs:
            return True
        return False

    @staticmethod
    def get_file_name_from_path(path, no_suffix_flag):
        """"""
        ret = ntpath.basename(path)
        if no_suffix_flag:
            tup = os.path.splitext(ret)
            ret = tup[0]
        return ret

    @staticmethod
    def get_base_rev_name(full_rev_name):
        """"""
        return full_rev_name.rsplit("/", 1)[1]

    @staticmethod
    def is_valid_revision(rev):
        """"""
        if not SGlobalFuncs.is_valid_git_commit_hash(rev) and \
           not SGlobalFuncs.is_valid_git_branch_name(rev) and \
           not SGlobalFuncs.is_valid_git_tag_name(rev):
            return False
        return True

    @staticmethod
    def is_valid_git_ref_name(ref):
        """"""
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
        """"""
        if len(commit_hash) != HASH_FIXED_LEN:
            return False
        try:
            int(commit_hash, 16)
        except ValueError:
            return False
        return True

    @staticmethod
    def is_valid_git_branch_short_name(branch_name):
        """"""
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
        """Returns True is 'branch_name' is a valid git branch name"""
        if not branch_name.startswith(REF_BRANCH_PREFIX):
            return False
        return SGlobalFuncs.is_valid_git_ref_name(branch_name)

    @staticmethod
    def is_valid_git_tag_name(tag_name):
        if not tag_name.startswith(REF_TAG_PREFIX):
            return False
        return SGlobalFuncs.is_valid_git_ref_name(tag_name)

    @staticmethod
    def clone_repo(dest_full_path, url, checkout_rev_name="refs/heads/master"):
        """
        clone a repository from 'url' into path 'dest_full_path' and checkout
        revision 'checkout_rev_name'
        returns a cloned repository object
        """
        is_commit_hash = False
        if (SGlobalFuncs.is_valid_git_branch_name(checkout_rev_name) and
                SGlobalFuncs.is_branch_exist_in_remote_repo(url,
                                                            checkout_rev_name,
                                                            False)):
            co_branch = SGlobalFuncs.get_base_rev_name(checkout_rev_name)
        elif (SGlobalFuncs.is_valid_git_tag_name(checkout_rev_name) and
              SGlobalFuncs.is_tag_exist_in_remote_repo(url,
                                                       checkout_rev_name,
                                                       False)):
            co_branch = SGlobalFuncs.get_base_rev_name(checkout_rev_name)
        elif SGlobalFuncs.is_valid_git_commit_hash(checkout_rev_name):
            co_branch = checkout_rev_name
            is_commit_hash = True
        else:
            raise ValueError(
                "Invalid checkout_rev_name %s to checkout after cloning!"
                % checkout_rev_name)

        # create folder if not exist
        if not os.path.exists(dest_full_path):
            logger.info("Creating new folder %s" % dest_full_path)
            os.makedirs(dest_full_path)

        # now clone
        if is_commit_hash:
            logger.info("Cloning repository {} to {} and checking out "
                        "commit hash {}".format(
                                                url,
                                                dest_full_path,
                                                co_branch))
            cloned_repo = Repo.clone_from(url, dest_full_path)
            cloned_repo.git.checkout(co_branch)
        else:
            cloned_repo = Repo.clone_from(
                url,
                dest_full_path,
                branch=co_branch)
            logger.info("Cloning repository {} to {} and checking out "
                        "branch {}".format(url, dest_full_path, co_branch))

        assert cloned_repo.__class__ is Repo
        return cloned_repo

#
#   Class CRepoManifestFile
#


class CRepoManifestFile(object):
    """This class stores information about manifest XML file in
    armmbed/mbl-manifest repository """

    def __init__(self, path, filename, tree, root, default_rev,
                 remote_key_to_remote_dict, repo_name_to_proj_dict):

        # path + short_name (with no suffix)
        self.path = path
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

        logger.debug("Created new {} : {}".format(
            type(self).__name__, pformat(locals())))

#
#   Class CRepoManifestProject
#


class CRepoManifestProject(object):
    """
    This class represents a google repo manifest file 'project' entry that
    needs to be cloned.
    Each CRepoManifestFile holds one or more CRepoManifestProject objects
    inside repo_name_to_proj_dict.
    """

    def __init__(self, full_name, prefix,
                 short_name, remote_key, url, revision):
        """"""
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
        # prefix -> MRR_URL_PREFIX = "armmbed"
        if ((self.name_prefix == ARM_MRR_REPO_NAME_PREFIX) and
                (self.remote_key == MRR_MANIFEST_REMOTE_KEY)):
            self.isArmMRR = True
        else:
            self.isArmMRR = False

        logger.debug("Created new {} : {}".format(
            type(self).__name__, pformat(locals())))

#
#   Class CGitClonedRepository
#


class CGitClonedRepository(object):
    """
    This class represents a cloned repository
    All cloned repositories are kept under
    CRepoManifestProject cloned_repo or
    CReleaseManager::additional_repo_name_to_cloned_repo_dict
    """

    def __init__(self, remote, name_prefix, short_name,
                 clone_base_path, checkout_rev):

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
        self.url = SGlobalFuncs.build_url_from_base_repo_name(
            remote, name_prefix, short_name)

        # clone and get git.Repo object
        if (self.checkout_rev.startswith(REF_BRANCH_PREFIX) or
            self.checkout_rev.startswith(REF_TAG_PREFIX) or
                len(self.checkout_rev) == HASH_FIXED_LEN):

            self.handle = SGlobalFuncs.clone_repo(
                self.clone_dest_path, self.url, self.checkout_rev)
        else:

            # try to clone as branch
            try:
                self.handle = SGlobalFuncs.clone_repo(
                    self.clone_dest_path,
                    self.url,
                    REF_BRANCH_PREFIX + self.checkout_rev)

            except ValueError:
                # try to clone as tag
                self.handle = SGlobalFuncs.clone_repo(
                    self.clone_dest_path, self.url, self.checkout_rev)

        logger.debug("Created new {} : {}".format(
            type(self).__name__, pformat(locals())))
        logger.info("{} Cloned from remote {} to folder {}".format(
            self.full_name, self.url, self.clone_dest_path))

#
# CReleaseManager
#


class CReleaseManager(object):
    """The main class. Represents a release manager object"""

    def __init__(self):

        # initialize logger  - set logging level to INFO at this initial stage.
        # Each log entry will be at least 2 lines.
        logging.basicConfig(level=logging.INFO, format=LOGGING_REGULAR_FORMAT)

        logger.info("Creating {} version {}".format(module_name, __version__))

        # list of CRepoManifestFile objects
        self.manifest_file_name_to_obj_dict = {}

        # mark success for destructor
        self.completed = False

        """
        Dictionary of CGitClonedRepository objects. Carry only cloned
        repositories under  ADDITIONAL_SD_KEY_NAME section other manifest git
        repositories are kept per project
        (CRepoManifestProject:cloned_repo object).
        Key - repo name
        value - cloned CGitClonedRepository
        """
        self.additional_repo_name_to_cloned_repo_dict = {}

        # starting revision for mbl-manifest
        self.mbl_manifest_clone_ref = ""

        """
        Dictionary of dictionaries created from user input JSON file
        Key - file name or the special keys
            COMMON_SD_KEY_NAME, ADDITIONAL_SD_KEY_NAME
        value - a sub dictionary for this category. The common category will
            set the revision for all projects in all xml files while other
            categories are file specific.
        Each sub-dictionary holds pairs of full repository names and a target
        revision to replace in XML files and (if type permits) to create
        branch/tag on remote.
        """
        self.new_revisions_dict = {}

        """
        list of tuples CGitClonedRepository  which have already been updated
        and pushed to remote. In case of an error all remotes revisions must
        be deleted
        """
        self.already_pushed_repository_list = []

        # parse arguments
        parser = self.get_argument_parser()
        self.args = parser.parse_args()

        # Set verbose log level if enabled by user and log command
        # line arguments
        if self.args.verbose:
            logger.setLevel(logging.DEBUG)
        logger.debug("Command line arguments:{}".format(self.args))

        # create a temporary folder to clone repositories in
        while True:
            random_str = ''.join(
                random.choice(string.ascii_lowercase) for m in range(8))
            path = os.path.join(
                tempfile.gettempdir(), "mbl_" + random_str)
            if not os.path.exists(path):
                os.makedirs(path)
                self.tmp_dir_path = path
                break

        logger.info("Temporary folder: %s" % self.tmp_dir_path)

        logger.debug(
            "Created new {} : {}".format(
                type(self).__name__, pformat(locals())))

    def __enter__(self):
        """"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """deletes all already-pushed references in case of a failure"""
        if not self.completed and len(self.already_pushed_repository_list) > 0:
            logger.error("Removing all pushed references : %s" %
                         self.already_pushed_repository_list)
            for repo, ref in self.already_pushed_repository_list:
                repo.handle.remotes.origin.push(":" + ref.path)

        if self.args.remove_temporary_folder:
            logger.info("Removing temporary folder %s" %
                        self.tmp_dir_path)
            shutil.rmtree(self.tmp_dir_path)

    def _repo_push(self, repo, new_rev):
        """push a revision to remote repository"""
        _str = "Pushing {} to repository {} url {}".format(
                new_rev, repo.full_name, repo.url)
        if self.args.simulate:
            logger.info("Virtually " + _str)
        else:
            logger.info(_str)
            repo.handle.git.push(GIT_REMOTE_NAME, new_rev)
            self.already_pushed_repository_list.append((repo, new_rev))

    def process_manifest_files(self):
        """parse, validate and modify XML manifest files"""

        logger.info("Parse, validate and modify XML manifest files...")
        adict = self.additional_repo_name_to_cloned_repo_dict

        # clone mbl-manifest repository first and checkout mbl_
        # manifest_clone_ref
        logger.info(
            "Cloning repository %s checkout branch %s" %
            (MBL_MANIFEST_REPO_NAME, self.mbl_manifest_clone_ref))

        adict[MBL_MANIFEST_REPO_NAME] = \
            self.create_and_update_new_revisions_worker(
                ARM_MRR_REMOTE,
                ARM_MRR_REPO_NAME_PREFIX,
                MBL_MANIFEST_REPO_SHORT_NAME,
                self.tmp_dir_path,
                self.mbl_manifest_clone_ref,
                self.new_revisions_dict[
                    ADDITIONAL_SD_KEY_NAME][MBL_MANIFEST_REPO_NAME][1])

        # get all files ending with .xml inside this directory.
        # We assume they are all manifest files
        xml_file_list = []
        path = os.path.join(
            adict[
                MBL_MANIFEST_REPO_NAME].clone_dest_path,
            "*.xml")
        for file_name in glob.glob(path):
            xml_file_list.append(os.path.abspath(file_name))

        if xml_file_list:
            logger.info("Found xml to parse : %s" % pformat(xml_file_list))

        '''
        We are interested in 3 sub-elements types :
        1. 'default' : defult fetch attributes. Types:
            a. 'revision' - default revision in case that revision=None in
            project definition
        2. 'remote' : remote repository UTL attributes
            a. 'fetch' - base fetch URL (prefix)
            b. 'name' - this name is the key to the matching fetch attribute
        3. 'project' - each project describes an MRR. Types:
            a. 'name' - repository prefix concatenated with the repository
                short name
            b. 'remote' - 2.b name - should be replace with fetch in order to
                fetch the repository
            c. 'revision' - this one is optional tag or branch (head) name.
                If not exist, assign revision from 1.a
        '''
        # parse all xml files, create a CRepoManifestFile object for each and
        # store in manifest_file_name_to_obj_dict
        for file_path in xml_file_list:
            logger.debug("Start parsing file %s" % file_path)

            # get root
            tree = ElementTree.parse(file_path)

            # root element of the tree
            root = tree.getroot()

            # get default, if not found, set to master
            node = tree.find('./default')
            default_rev = "master"
            if node:
                default_rev = node.get("revision", "master")

            # get remotes - store in a dictionary
            # { remote key : remote URL prefix }
            remote_key_to_remote_dict = {}
            for atype in root.findall('remote'):
                remote_key_to_remote_dict[atype.get(
                    'name')] = atype.get('fetch')

            # get projects - store in a short project name to
            base_name = ""
            name_to_proj_dict = {}
            is_change = False
            for atype in root.findall('project'):
                # get name and split to prefix and short name
                full_name = atype.get('name')
                prefix, short_name = full_name.rsplit('/', 1)
                if short_name in name_to_proj_dict:
                    raise ValueError(
                        "File %s : project %s repeats multiple times!".format(
                            file_path, short_name))

                # get remote key and build url
                remote_key = atype.get('remote')
                url = \
                    remote_key_to_remote_dict[remote_key] + \
                    ":/" + \
                    full_name + \
                    ".git"

                # get and set new revision
                revision = atype.get('revision')
                if not revision:
                    revision = default_rev

                base_name = SGlobalFuncs.get_file_name_from_path(
                    file_path, True)

                # create project and insert to dictionary
                proj = CRepoManifestProject(
                    full_name, prefix, short_name, remote_key, url, revision)
                name_to_proj_dict[full_name] = proj

                # set the new revision, that will save time,
                # we are already in the place we want to change!
                new_ref = self.get_new_ref_from_new_revision_dict(
                    base_name, full_name)
                if new_ref == REF_BRANCH_PREFIX + default_rev:
                    del atype.attrib["revision"]
                    is_change = True
                else:
                    if new_ref:
                        atype.set('revision',
                                  SGlobalFuncs.get_base_rev_name(new_ref))
                        is_change = True
            assert base_name

            rmf = CRepoManifestFile(
                file_path, base_name,
                tree,
                root,
                default_rev,
                remote_key_to_remote_dict,
                name_to_proj_dict)
            self.manifest_file_name_to_obj_dict[base_name] = rmf

            if is_change:
                # backup file
                summary_log_list.append(
                    SUMMARY_H_BKP +
                    "Created back file %s from %s" %
                    (file_path + FILE_BACKUP_SUFFIX, file_path))
                logger.info(
                    "Created backup file %s from %s" %
                    (file_path + FILE_BACKUP_SUFFIX, file_path))
                copyfile(file_path, file_path + FILE_BACKUP_SUFFIX)

                # write to file
                rmf.tree.write(file_path)
                summary_log_list.append(
                    SUMMARY_H_MODIFY_FILE +
                    "File %s has been modified on repository %s" %
                    (file_path, MBL_MANIFEST_REPO_NAME))

                logger.info("File %s has been modified!" % file_path)

    @staticmethod
    def validate_remote_repositories_state_helper(url, new_rev):
        """check that new rev does not exist on remote"""
        if new_rev.startswith(REF_BRANCH_PREFIX):
            return SGlobalFuncs.is_branch_exist_in_remote_repo(
                url, new_rev, False)
        if new_rev.startswith(REF_TAG_PREFIX):
            return SGlobalFuncs.is_tag_exist_in_remote_repo(
                url, new_rev, False)

        return True  # fail

    def validate_remote_repositories_state(self):
        """check that all branches/tags to be created, are not on remote"""

        logger.info("Validating remote repositories state...")

        '''
        list of  tuples. Each tuple is of length of 2:
        index 0 : URL to check
        index 1 : revision to check
        '''
        idx_url = 0
        idx_rev = 1
        check_remote_list = []

        # add all entries from ADDITIONAL_SD_KEY_NAME SD:
        for (k, v) in self.new_revisions_dict[ADDITIONAL_SD_KEY_NAME].items():
            url = SGlobalFuncs.build_url_from_repo_name(ARM_MRR_REMOTE, k)
            check_remote_list.append((url, v[1]))

        for file_obj in self.manifest_file_name_to_obj_dict.values():
            # file_obj is CRepoManifestFile
            for (k, v) in file_obj.repo_name_to_proj_dict.items():
                # k is a repository name and v is a matching project

                url = SGlobalFuncs.build_url_from_repo_name(
                    file_obj.remote_key_to_remote_dict[v.remote_key],
                    v.full_name)

                new_ref = self.get_new_ref_from_new_revision_dict(
                    file_obj.filename, k)

                if not new_ref:
                    continue
                if v.isArmMRR:
                    # for Arm MRRs check both current revision and new revision
                    # (since we need to clone and change branch from)
                    check_remote_list.append((url, new_ref))

        logger.debug("===check_remote_list:")
        logger.debug(pformat(check_remote_list))

        # check concurrently that none of the repositories in mrr_url_set
        # has a branch called 'create_branch_name'
        logger.info("Starting %d concurrent threads to validate "
                    "remote repositories state..."
                    % len(check_remote_list))
        with concurrent.futures.ThreadPoolExecutor(
                max_workers=len(check_remote_list)) as executor:

            future_to_git_url = {
                executor.submit(
                    self.validate_remote_repositories_state_helper,
                    tup[idx_url],
                    tup[idx_rev]):

                tup for tup in check_remote_list
            }

            for future in concurrent.futures.as_completed(
                    future_to_git_url,
                    MAX_TMO_SEC):
                tup = future_to_git_url[future]
                result = future.result()
                if result:
                    raise argparse.ArgumentTypeError(
                        "revision {} exist on remote url {}".format(
                            tup[idx_rev], tup[idx_url]))

        logger.info("Worker threads done...")

    @staticmethod
    def dict_raise_on_duplicates(ordered_pairs):
        """Raise an ValueError exception if find duplicate keys."""
        d = {}
        for k, v in ordered_pairs:
            if k in d:
                raise ValueError("duplicate key: %r" % (k,))
            else:
                d[k] = v
        return d

    def validate_cross_dependencies(self):
        """
        Check that :
        1. All file-specific SDs point to actual files
        2. All repository names in SDs points to at least one actual project
            in manifest files if they are in sd name COMMON_SD_KEY_NAME
            (case B), or if the sd is file specific it must point to a project
            which can be found in that file (case A)
        """

        logger.info(
            "Validating cross dependencies (input file vs manifest files)...")

        for file_name, sd in self.new_revisions_dict.items():
            if file_name == ADDITIONAL_SD_KEY_NAME:
                continue

            # checking 1
            if file_name != COMMON_SD_KEY_NAME:
                found = file_name in self.manifest_file_name_to_obj_dict
                if not found:
                    mbl_manifest_path = \
                        self.additional_repo_name_to_cloned_repo_dict[
                            MBL_MANIFEST_REPO_NAME].clone_dest_path
                    raise ValueError(
                        "main entry key {} in user input file "
                        "is not found in {}".format(
                            file_name,
                            os.path.join(
                                mbl_manifest_path, file_name + ".xml")))

            # checking 2
            for repo_name in sd:
                found = False
                if file_name != COMMON_SD_KEY_NAME:
                    found = repo_name in self.manifest_file_name_to_obj_dict[
                        file_name].repo_name_to_proj_dict
                else:
                    for f in self.manifest_file_name_to_obj_dict.values():
                        if repo_name in f.repo_name_to_proj_dict:
                            found = True
                            break
                if not found:
                    raise ValueError(
                        "invalid input file :"
                        " entry ({}, {}) not found!".format(
                            file_name, repo_name))

        self.validate_remote_repositories_state()

    def parse_and_validate_input_file(self):
        """"""
        logger.info("Parsing and validating input file %s..." %
                    self.args.refs_input_file_path)

        # Open the given input and parse into new_revision_dict dictionary,
        # detect duplicate main key
        with open(
                self.args.refs_input_file_path, encoding='utf-8') as data_file:
            try:
                nrd = json.loads(
                    data_file.read(),
                    object_pairs_hook=self.dict_raise_on_duplicates)
            except json.decoder.JSONDecodeError as err:
                logger.info("Illegal json file!!", err)
                sys.exit(-1)

        """
        Check that exist at least ADDITIONAL_SD_KEY_NAME key with a
        sub-dictionary that comply with :
        1. All pairs are (key, lists of length 2), and the value list must
        have distinct values.
        2. armmbed/mbl-manifest repository exist in sub-dictionary
        """
        if ADDITIONAL_SD_KEY_NAME not in nrd:
            raise ValueError(
                "main entry key %s could not be found in user input file" %
                ADDITIONAL_SD_KEY_NAME)
        if MBL_MANIFEST_REPO_NAME not in nrd[ADDITIONAL_SD_KEY_NAME]:

            raise ValueError(
                "%s key is not found could not be found in user input "
                "file under %s" %
                (MBL_MANIFEST_REPO_NAME, ADDITIONAL_SD_KEY_NAME))

        for l in nrd[ADDITIONAL_SD_KEY_NAME].values():
            if len(l) != 2:
                raise ValueError(
                    "Bad length for list %s - All lists under key %s in user "
                    "input file must be of length 2!" %
                    (l, ADDITIONAL_SD_KEY_NAME))

            if l[0] == l[1]:
                raise ValueError("Bad list %s - non-distinct values under "
                                 "key %s in user input file!" %
                                 (l, ADDITIONAL_SD_KEY_NAME))

        # set the clone ref for mbl-manifest
        self.mbl_manifest_clone_ref = \
            nrd[ADDITIONAL_SD_KEY_NAME][MBL_MANIFEST_REPO_NAME][0]

        """
        do not allow any repo name under common SD to appear in any other SD
        pair as key do not allow any repo name under additional SD to appear in
        any other SD pair as key l carry a merged list of all pairs which are
        not in common/additional SDs
        """
        validation_list = []
        for (key, val) in nrd.items():
            if (key != COMMON_SD_KEY_NAME) and (key != ADDITIONAL_SD_KEY_NAME):
                validation_list += val
        if validation_list:
            if COMMON_SD_KEY_NAME in nrd:
                for key in nrd[COMMON_SD_KEY_NAME].keys():
                    if key in validation_list:
                        raise ValueError("Invalid input in file {} : key {} "
                                         "found in {} but also in other file "
                                         "specific file SDs!".format(
                                            self.args.refs_input_file_path,
                                            key,
                                            COMMON_SD_KEY_NAME))

            if ADDITIONAL_SD_KEY_NAME in nrd:
                for key in nrd[ADDITIONAL_SD_KEY_NAME].keys():
                    if key in validation_list:
                        raise ValueError(
                            "Invalid input in file {} : key {} found in {}, "
                            "but also in other file specific file SDs!".format(
                                self.args.refs_input_file_path,
                                key,
                                ADDITIONAL_SD_KEY_NAME))

        # do not allow for the same repo name in file specific SD to have the
        # same branch name, or the same tag name (equal tag and branch name
        # in separate repos is allowed, but not recommended!)
        tup_list = []
        for (sd_name, sd) in nrd.items():
            if sd_name in [ADDITIONAL_SD_KEY_NAME, COMMON_SD_KEY_NAME]:
                continue
            tup_list += [(v, k) for k, v in sd.items()]
        for t in tup_list:
            if tup_list.count(t) > 1:
                raise ValueError(
                    "Invalid input file %s : The pair %s appears in more "
                    "than one file specific SD!" %
                    (self.args.refs_input_file_path, t))

        self.new_revisions_dict = nrd

    def get_new_ref_from_new_revision_dict(self, sd_key_name, repo_name):
        """"""
        if ((sd_key_name in self.new_revisions_dict) and
                (repo_name in self.new_revisions_dict[sd_key_name])):

            if sd_key_name == ADDITIONAL_SD_KEY_NAME:
                return self.new_revisions_dict[sd_key_name][repo_name][1]
            return self.new_revisions_dict[sd_key_name][repo_name]

        if repo_name in self.new_revisions_dict[COMMON_SD_KEY_NAME]:
            return self.new_revisions_dict[COMMON_SD_KEY_NAME][repo_name]

        return None

    def create_and_update_new_revisions_worker(
            self, remote, name_prefix, short_name,
            clone_base_path, cur_rev, new_rev):
        """"""

        repo = CGitClonedRepository(
            remote, name_prefix, short_name, clone_base_path, cur_rev)

        new_rev_short = new_rev.rsplit("/", 1)[1]

        # Create the new branch/tag
        if new_rev.startswith(REF_BRANCH_PREFIX):
            prev = repo.handle.active_branch
            new_branch = repo.handle.create_head(new_rev_short)
            assert new_branch.commit == repo.handle.active_branch.commit
            new_branch.checkout()
            new_rev = new_branch

            summary_log_list.append(
                SUMMARY_H_BRANCH +
                "Created and checkout new branch %s from branch HEAD %s "
                "on repository % s" %
                (new_rev_short, prev.name, repo.full_name))
        else:
            new_tag = repo.handle.create_tag(
                new_rev_short, ref=repo.handle.active_branch.commit)
            assert new_tag.commit == repo.handle.active_branch.commit
            assert new_tag.tag is None
            new_rev = new_tag

            summary_log_list.append(
                SUMMARY_H_TAG +
                "Created and checkout new tag %s on commit %s on "
                "repository % s" % (
                    new_rev_short,
                    repo.handle.active_branch.commit.hexsha,
                    repo.full_name))

        if repo.full_name not in \
                [MBL_MANIFEST_REPO_NAME, MBL_LINKED_REPOSITORIES_REPO_NAME]:
            if self.diag_repo_push(repo):
                self._repo_push(repo, new_rev)
                summary_log_list.append(
                    SUMMARY_H_PUSH +
                    "Pushed from repository clone path={} a new branch={} "
                    "to remote url={}".format(
                        repo.clone_dest_path,
                        repo.handle.active_branch.name,
                        repo.url))
            else:
                logger.info("Skip pushing...")

        return repo

    def update_mbl_linked_repositories_conf_helper(self, git_repo):
        """"""

        logger.info("Start updating file %s in repository %s (if needed)" %
                    (MBL_LINKED_REPOSITORIES_REPO_PATH,
                     MBL_LINKED_REPOSITORIES_REPO_NAME))

        # check if file exist
        file_path = os.path.join(
            git_repo.clone_dest_path, MBL_LINKED_REPOSITORIES_REPO_PATH)
        if not os.path.exists(file_path):
            raise FileNotFoundError("File %s not found!" % file_path)

        # Create backup
        logger.info("Created backup file %s from %s" %
                    (file_path + FILE_BACKUP_SUFFIX, file_path))
        summary_log_list.append(
            SUMMARY_H_BKP +
            "Created back file %s from %s" %
            (file_path + FILE_BACKUP_SUFFIX, file_path))
        copyfile(file_path, file_path + FILE_BACKUP_SUFFIX)

        """
        Open the file, traverse all over the ADDITIONAL_SD_KEY_NAME SD
        repositories, and replace We expect file structure, where each element
        represents a linked repository has 3 settings :
        1) options
        2) repo URL
        3) SRCREV in that order
            We are going to locate the repo name and change the SRCREV
        """
        is_changed = False
        d = self.additional_repo_name_to_cloned_repo_dict
        for repo_name in \
                self.new_revisions_dict[ADDITIONAL_SD_KEY_NAME].keys():
            if repo_name not in [MBL_MANIFEST_REPO_NAME,
                                 MBL_LINKED_REPOSITORIES_REPO_NAME]:

                with in_place.InPlace(file_path) as file:
                    next_line_replace = False
                    for line in file:
                        if line.lower().find(
                                "git@github.com/" + repo_name) != -1:
                            active_branch = d[repo_name].handle.active_branch
                            commit_hash = active_branch.commit
                            branch_name = active_branch.name

                            if line.find(";branch=") != -1:
                                # match text between two quotes
                                matches = re.findall(r';branch=(.+?);', line)
                                for m in matches:
                                    line = line.replace(
                                        ';%s;' % m,
                                        ';branch=%s;' % branch_name)
                                    is_changed = True

                            # TODO : replace former line or reformat file..
                            next_line_replace = True
                        elif next_line_replace:
                            if (line.find("\"") == line.rfind("\"") or
                                    line.count("\"") != 2):
                                raise SyntaxError(
                                    "Bad format for file [{}] "
                                    "in line [{}]".format(file_path, line))

                            # match text between two quotes
                            matches = re.findall(r'\"(.+?)\"', line)
                            for m in matches:
                                line = line.replace(
                                    '\"%s\"' % m, '\"%s\"' % commit_hash)
                                is_changed = True
                            next_line_replace = False
                        file.write(line)

        if is_changed:
            ret_list = git_repo.handle.index.add([file_path], write=True)
            assert len(ret_list) == 1
            git_repo.handle.index.commit(
                "%s Automatic Commit Message" % module_name)
            logger.info("File %s has been modified and committed" % file_path)
            summary_log_list.append(
                SUMMARY_H_MODIFY_FILE +
                "File %s has been modified and committed on repository %s" %
                (file_path, git_repo.full_name))

        if self.diag_repo_push(git_repo):
            self._repo_push(git_repo, git_repo.handle.active_branch)
            summary_log_list.append(
                SUMMARY_H_PUSH +
                "Pushed from repository clone path={} a new branch={} "
                "to remote url={},"
                "\nNew commit hash={}".format(
                    git_repo.clone_dest_path,
                    git_repo.handle.active_branch.name,
                    git_repo.url,
                    git_repo.handle.active_branch.commit.hexsha))
        else:
            logger.info("Skip pushing...")

    def update_mbl_linked_repositories_conf(self):
        """"""
        # update all MBL_LINKED_REPOSITORIES_REPO_NAME repositories
        d = self.additional_repo_name_to_cloned_repo_dict
        if MBL_LINKED_REPOSITORIES_REPO_NAME in d:
            self.update_mbl_linked_repositories_conf_helper(
                d[MBL_LINKED_REPOSITORIES_REPO_NAME])
        for fo in self.manifest_file_name_to_obj_dict.values():
            if MBL_LINKED_REPOSITORIES_REPO_NAME in fo.repo_name_to_proj_dict:
                self.update_mbl_linked_repositories_conf_helper(
                    fo.repo_name_to_proj_dict[
                        MBL_LINKED_REPOSITORIES_REPO_NAME].cloned_repo)

    def diag_repo_push(self, repo):
        """diagnostic mode - before pushing.
        returns True if program should push"""

        if self.args.diagnostic_mode:
            print("\n=============================")
            print("Diagnostic Mode - BEFORE PUSH TO REMOTE")
            print("New branch : %s" % repo.handle.active_branch.name)
            if repo.full_name in [MBL_MANIFEST_REPO_NAME,
                                  MBL_LINKED_REPOSITORIES_REPO_NAME]:
                print("New Commit SHA : %s" %
                      repo.handle.active_branch.commit.hexsha)

            print("Remote URL : %s" % repo.url)
            print("Repository clone path : %s" % repo.clone_dest_path)
            answer = input(
                "Press n/N to continue without pushing, "
                "q/Q to quit, "
                "or any other key to continue : ")

            if answer.lower() == 'q':
                sys.exit(0)
            if answer.lower() == 'n':
                return False
        return True

    def mbl_manifest_repo_push(self):
        repo = self.additional_repo_name_to_cloned_repo_dict[
            MBL_MANIFEST_REPO_NAME]
        repo.handle.git.add(update=True)
        repo.handle.index.commit("release manager automatic commit")

        if self.diag_repo_push(repo):
            self._repo_push(repo, repo.handle.active_branch)
            summary_log_list.append(
                SUMMARY_H_PUSH +
                "Pushed from repository clone path={} a new "
                "branch={} to remote url={},"
                "\nNew commit hash={}".format(
                    repo.clone_dest_path,
                    repo.handle.active_branch.name,
                    repo.url,
                    repo.handle.active_branch.commit.hexsha))
        else:
            logger.info("Skip pushing...")

    def clone_and_create_new_revisions(self):
        """Clone all additional and Arm MRR repositories,
        concurrently, checkout current revision"""

        logger.info("Cloning and creating new revisions...")

        # list of tuples
        clone_tup_list = []
        # clone all additional repositories under self.tmp_dir_path
        for (main_key, sd) in self.new_revisions_dict.items():
            for (key, rev) in sd.items():
                if main_key == ADDITIONAL_SD_KEY_NAME:
                    if key != MBL_MANIFEST_REPO_NAME:
                        prefix, name = key.rsplit("/", 1)
                        clone_tup_list.append(
                            # tuple
                            (key,
                             ARM_MRR_REMOTE,
                             prefix,
                             name,
                             self.tmp_dir_path,
                             rev[0],
                             rev[1], main_key)
                        )

        """
        Clone all Arm MRRs, each one on a sub-folder belong to the file.
        For example, for default.xml, all matching repos will be cloned
        under <self.tmp_dir_path>/default
        """
        for f in self.manifest_file_name_to_obj_dict.values():
            for (name, proj) in (f.repo_name_to_proj_dict.items()):
                new_ref = self.get_new_ref_from_new_revision_dict(
                    f.filename, proj.full_name)
                if proj.isArmMRR and new_ref:
                    prefix, name = proj.full_name.rsplit("/", 1)

                    clone_tup_list.append(
                        # tuple
                        (
                            proj.full_name,
                            f.remote_key_to_remote_dict[proj.remote_key],
                            prefix,
                            name,
                            os.path.join(self.tmp_dir_path, f.filename),
                            proj.revision,
                            new_ref,
                            f.filename)
                    )

        logger.debug("=== clone_tup_list:")
        logger.debug(pformat(clone_tup_list))

        logger.info("Starting %d concurrent threads to clone repositories..." %
                    len(clone_tup_list))
        with concurrent.futures.ThreadPoolExecutor(
                max_workers=len(clone_tup_list)) as executor:

            future_to_git_url = {
                executor.submit(
                    self.create_and_update_new_revisions_worker,
                    tup[1], tup[2], tup[3], tup[4], tup[5], tup[6]):
                tup for tup in clone_tup_list
            }

            for future in concurrent.futures.as_completed(
                    future_to_git_url, MAX_TMO_SEC):

                tup = future_to_git_url[future]
                result = future.result()
                if not result:
                    raise argparse.ArgumentTypeError(
                        "revision {} exist on remote url {}".format(
                            tup[1], tup[0]))
                else:
                    if tup[7] == ADDITIONAL_SD_KEY_NAME:
                        self.additional_repo_name_to_cloned_repo_dict[
                            tup[0]] = result
                    else:
                        odict = self.manifest_file_name_to_obj_dict[tup[7]]
                        pdict = odict.repo_name_to_proj_dict[tup[0]]
                        pdict.cloned_repo = result
        logger.info("Worker threads done...")

    def print_summary(self, start_time):
        """print summary in different formatting"""

        hdlr = logger.root.handlers[0]
        hdlr.setFormatter(logging.Formatter(LOGGING_SUMMARY_FORMAT))

        logger.info("\n\n")
        logger.info("===============================================")
        logger.info("=== === === === === SUCCESS === === === === ===")
        logger.info("===============================================\n")

        if not self.args.remove_temporary_folder:
            logger.info("Temporary folder: %s" % self.tmp_dir_path)
        logger.info("Time running: %s" % int(time.time() - start_time))

        logger.info("\n== Event log ==\n")
        for idx, ev in enumerate(summary_log_list):
            logger.info("{}. {}".format(idx+1, ev))
            logger.info("-----")

        hdlr = logger.root.handlers[0]
        hdlr.setFormatter(logging.Formatter(LOGGING_REGULAR_FORMAT))

    class StoreValidFile(argparse.Action):
        """argparse gelper class - Costume action - check that the given file
        path exist on local host"""

        def __call__(self, parser, namespace, values, option_string=None):
            file_path = os.path.abspath(values)
            if not os.path.isfile(file_path):
                raise argparse.ArgumentTypeError(
                    "The path %s does not exist!" % file_path
                )
            filename, file_extension = os.path.splitext(
                ntpath.basename(file_path))
            if not file_extension == ".json":
                raise argparse.ArgumentTypeError(
                    "File %s does not end with '.json' prefix!" % file_path
                )
            setattr(namespace, self.dest, file_path)

    def get_argument_parser(self):
        """define and parse script input arguments"""
        parser = argparse.ArgumentParser(
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            description=module_name + " script",
        )

        parser.add_argument(
            "refs_input_file_path",
            action=self.StoreValidFile,
            help="path to update.json file which holds a dictionary of pairs "
                 "(repository name, branch / tag / hash)."
                 "For more information and exact format "
                 "see mbl-tools/build-mbl/README.md."
        )

        parser.add_argument(
            "-v",
            "--verbose",
            help="verbose logging - prints all logs",
            action="store_true"
        )

        parser.add_argument(
            "-d",
            "--diagnostic_mode",
            help="diagnostic mode - prompts before each significant step, "
                 "allowing user to check changes in files and repositories",
            action="store_true"
        )

        parser.add_argument(
            "-s",
            "--simulate",
            help="do not push to remote, everything else will be executed "
                 "exactly the same but nothing is actually pushed into "
                 "remote.",
            action="store_true"
        )

        parser.add_argument(
            "-r",
            "--remove_temporary_folder",
            help="On competition, remove the temporary folder and all of its "
                 "content",
            action="store_true"
        )

        return parser


def _main():

    with CReleaseManager() as rm:

        start_time = time.time()

        # Parse JSON references input file
        rm.parse_and_validate_input_file()

        # Clone the manifest repository and parse its xml files into database
        rm.process_manifest_files()

        # Some more things to validate between input and manifest files file
        # after parsing both files
        rm.validate_cross_dependencies()

        # Update new_revision for all manifest files projects and create
        # reference (where needed on
        # remote Git repositories)
        rm.clone_and_create_new_revisions()

        # update all files MBL_LINKED_REPOSITORIES_REPO_PATH in repositories
        # MBL_LINKED_REPOSITORIES_REPO_NAME
        rm.update_mbl_linked_repositories_conf()

        # Commit MBL_LINKED_REPOSITORIES_REPO_NAME and MBL_MANIFEST_REPO_NAME
        # and push to remote
        rm.mbl_manifest_repo_push()

        # print summary
        rm.print_summary(start_time)

        # mark success
        rm.completed = True


if __name__ == "__main__":
    sys.exit(_main())

