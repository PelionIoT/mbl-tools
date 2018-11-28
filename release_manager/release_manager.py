# Copyright (c) 2017, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""
main module.

This module defines the script's main class CReleaseManager. It provides an API
 to entry point to preform the needed operations.It preforms
much of the script :
1) User input parsing, data validation.
2) Logging and diagnostics data storage and printing.
3) Creation of all other objects (manifest files and projects,
git repositories).
4) Cloning, committing branching and pushing data.
5) All functions called from the main entry point belong to CReleaseManager.
"""
#
# imports
#

import argparse
import logging
import random
import string
import tempfile
import json
import glob
import xml.etree.ElementTree as ElementTree
import concurrent.futures
import in_place
import re
import time
from pprint import pformat
from shutil import copyfile, rmtree
import sys

from git_clone import CGitClonedRepository
from git_utils import *
from repo_manifest import CRepoManifestProject, CRepoManifestFile
from main import program_name


#
# logging constants
#

LOGGING_REGULAR_FORMAT = (
    "\n%(asctime)s - %(name)s - "
    "{%(funcName)s:%(lineno)d} - "
    "%(levelname)s \n%(message)s"
)
LOGGING_SUMMARY_FORMAT = "%(message)s"

#
# constants
#

COMMON_SD_KEY_NAME = "_common_"
EXTERNAL_SD_KEY_NAME = "_external_"
MAX_TMO_SEC = 120


INPUT_FILE_NAME = "update.json"
FILE_BACKUP_SUFFIX = "~"

#
# remote URL constants
#

ARM_MRR_REMOTE = "ssh://git@github.com"
ARM_MRR_URL_PATTERN = "ssh://git@github.com:/{}/{}.git"

MBL_MANIFEST_REPO_SHORT_NAME = "mbl-manifest"
# armmbed/mbl-manifest
MBL_MANIFEST_REPO_NAME = "{}/{}".format(
    ARM_MRR_REPO_NAME_PREFIX, MBL_MANIFEST_REPO_SHORT_NAME
)
GIT_REMOTE_NAME = "origin"


#
# mbl-linked-repositories.conf update constants
#
MBL_LINKED_REPOSITORIES_REPO_SHORT_NAME = "meta-mbl"
MBL_LINKED_REPOSITORIES_REPO_NAME = "%s/%s" % (
    ARM_MRR_REPO_NAME_PREFIX,
    MBL_LINKED_REPOSITORIES_REPO_SHORT_NAME,
)
MBL_LINKED_REPOSITORIES_REPO_PATH = "conf/distro/mbl-linked-repositories.conf"


# list of strings to be printed at the script end, as a summary
summary_log_list = []
SUMMARY_H_PUSH = "PUSH: "
SUMMARY_H_MODIFY_FILE = "MODIFY FILE: "
SUMMARY_H_BKP = "CREATE BACKUP FILE: "
SUMMARY_H_BRANCH = "CREATE BRANCH: "
SUMMARY_H_TAG = "CREATE TAG: "

#
# CReleaseManager
#


class CReleaseManager(object):
    """
    class CReleaseManager.

    The main class. Represents a release manager object.
    """

    def __init__(self):
        """Object initialization."""
        # log the start time
        self.start_time = time.time()

        # initialize self.logger  - set logging level to INFO at this
        # initial stage. Each log entry will be at least 2 lines.
        logging.basicConfig(level=logging.INFO, format=LOGGING_REGULAR_FORMAT)
        self.logger = logging.getLogger(program_name)
        self.logger.info("Starting {}".format(program_name))

        # list of CRepoManifestFile objects
        self.manifest_file_name_to_obj_dict = {}

        # mark success for destructor
        self.completed = False

        """
        Dictionary of CGitClonedRepository objects. Carry only cloned
        repositories under  EXTERNAL_SD_KEY_NAME section other manifest git
        repositories are kept per project
        (CRepoManifestProject:cloned_repo object).
        Key - repo name
        value - cloned CGitClonedRepository
        """
        self.external_repo_name_to_cloned_repo_dict = {}

        # starting revision for mbl-manifest
        self.mbl_manifest_clone_ref = ""

        """
        Dictionary of dictionaries created from user input JSON file
        Key - file name or the special keys
            COMMON_SD_KEY_NAME, EXTERNAL_SD_KEY_NAME
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
            self.logger.setLevel(logging.DEBUG)
        self.logger.debug("Command line arguments:{}".format(self.args))

        # create a temporary folder to clone repositories in
        while True:
            random_str = "".join(
                random.choice(string.ascii_lowercase) for m in range(8)
            )
            path = os.path.join(tempfile.gettempdir(), "mbl_" + random_str)
            if not os.path.exists(path):
                os.makedirs(path)
                self.tmp_dir_path = path
                break

        self.logger.info("Temporary folder: %s" % self.tmp_dir_path)

        self.logger.debug(
            "Created new {} : {}".format(
                type(self).__name__, pformat(locals())
            )
        )

    def __enter__(self):
        """..."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Delete all already-pushed references in case of a failure."""
        if not self.completed and len(self.already_pushed_repository_list) > 0:
            self.logger.error(
                "Removing all pushed references : %s"
                % self.already_pushed_repository_list
            )
            for repo, ref in self.already_pushed_repository_list:
                repo.handle.remotes.origin.push(":" + ref.path)

        if self.args.remove_temporary_folder:
            self.logger.info(
                "Removing temporary folder %s" % self.tmp_dir_path
            )
            rmtree(self.tmp_dir_path)

    def repo_push(self, repo, new_rev):
        """push a revision to remote repository."""
        _str = "Pushing {} to repository {} url {}".format(
            new_rev, repo.full_name, repo.url
        )
        if self.args.simulate:
            self.logger.info("Virtually " + _str)
        else:
            self.logger.info(_str)
            try:
                repo.handle.git.push(GIT_REMOTE_NAME, new_rev)
                self.already_pushed_repository_list.append((repo, new_rev))
            except git.GitCommandError as err:
                # We've already checked that the branch does not exist.
                # That means it has been created by another concurrent thread
                if "reference already exists" not in err.stderr:
                    # re-raise the exception
                    raise

    def process_manifest_files(self):
        """parse, validate and modify XML manifest files."""
        self.logger.info("Parse, validate and modify XML manifest files...")
        adict = self.external_repo_name_to_cloned_repo_dict
        nrd = self.new_revisions_dict

        # clone mbl-manifest repository first and checkout mbl_
        # manifest_clone_ref
        self.logger.info(
            "Cloning repository %s checkout branch %s"
            % (MBL_MANIFEST_REPO_NAME, self.mbl_manifest_clone_ref)
        )

        adict[
            MBL_MANIFEST_REPO_NAME
        ] = self.create_and_update_new_revisions_worker(
            ARM_MRR_REMOTE,
            ARM_MRR_REPO_NAME_PREFIX,
            MBL_MANIFEST_REPO_SHORT_NAME,
            self.tmp_dir_path,
            self.mbl_manifest_clone_ref,
            nrd[EXTERNAL_SD_KEY_NAME][MBL_MANIFEST_REPO_NAME][1],
        )

        # get all files ending with .xml inside this directory.
        # We assume they are all manifest files
        xml_file_list = []
        path = os.path.join(
            adict[MBL_MANIFEST_REPO_NAME].clone_dest_path, "*.xml"
        )
        for file_name in glob.glob(path):
            xml_file_list.append(os.path.abspath(file_name))

        if xml_file_list:
            self.logger.info(
                "Found xml to parse : %s" % pformat(xml_file_list)
            )

        """
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
        """
        # parse all xml files, create a CRepoManifestFile object for each and
        # store in manifest_file_name_to_obj_dict
        for file_path in xml_file_list:
            self.logger.debug("Start parsing file %s" % file_path)

            # get root
            tree = ElementTree.parse(file_path)

            # root element of the tree
            root = tree.getroot()

            # get default, if not found, set to master
            node = tree.find("./default")
            default_rev = "master"
            if node:
                default_rev = node.get("revision", "master")

            # get remotes - store in a dictionary
            # { remote key : remote URL prefix }
            remote_key_to_remote_dict = {}
            for atype in root.findall("remote"):
                remote_key_to_remote_dict[atype.get("name")] = atype.get(
                    "fetch"
                )

            # get projects - store in a short project name to
            base_name = ""
            name_to_proj_dict = {}
            is_changed = False
            for atype in root.findall("project"):
                # get name and split to prefix and short name
                full_name = atype.get("name")
                prefix, short_name = full_name.rsplit("/", 1)
                if short_name in name_to_proj_dict:
                    raise ValueError(
                        "File %s : project %s repeats multiple times!".format(
                            file_path, short_name
                        )
                    )

                # get remote key and build url
                remote_key = atype.get("remote")
                url = (
                    remote_key_to_remote_dict[remote_key]
                    + ":/"
                    + full_name
                    + ".git"
                )

                # get and set new revision
                revision = atype.get("revision")
                if not revision:
                    revision = default_rev

                base_name = get_file_name_from_path(file_path, False)

                # create project and insert to dictionary
                proj = CRepoManifestProject(
                    full_name, prefix, short_name, remote_key, url, revision
                )
                name_to_proj_dict[full_name] = proj

                # set the new revision, that will save time,
                # we are already in the place we want to change!
                new_ref = self.get_new_ref_from_new_revision_dict(
                    base_name, full_name
                )
                if new_ref == REF_BRANCH_PREFIX + default_rev:
                    del atype.attrib["revision"]
                    is_changed = True
                elif new_ref:
                    if is_valid_git_commit_hash(new_ref):
                        atype.set("revision", new_ref)
                    else:
                        atype.set("revision", get_base_rev_name(new_ref))
                    is_changed = True

                if is_changed and "upstream" in atype.attrib:
                    # remove attribute 'upstream' is exist
                    del atype.attrib["upstream"]

            assert base_name

            rmf = CRepoManifestFile(
                file_path,
                base_name,
                tree,
                root,
                default_rev,
                remote_key_to_remote_dict,
                name_to_proj_dict,
            )
            self.manifest_file_name_to_obj_dict[base_name] = rmf

            if is_changed:
                # backup file
                summary_log_list.append(
                    SUMMARY_H_BKP
                    + "Created back file %s from %s"
                    % (file_path + FILE_BACKUP_SUFFIX, file_path)
                )
                self.logger.info(
                    "Created backup file %s from %s"
                    % (file_path + FILE_BACKUP_SUFFIX, file_path)
                )
                copyfile(file_path, file_path + FILE_BACKUP_SUFFIX)

                # write to file
                rmf.tree.write(file_path)
                summary_log_list.append(
                    SUMMARY_H_MODIFY_FILE
                    + "File %s has been modified on repository %s"
                    % (file_path, MBL_MANIFEST_REPO_NAME)
                )

                self.logger.info("File %s has been modified!" % file_path)

    @staticmethod
    def validate_remote_repositories_state_helper(url, new_rev):
        """Check that new rev does not exist on remote."""
        if new_rev.startswith(REF_BRANCH_PREFIX):
            return does_branch_exist_in_remote_repo(url, new_rev, False)
        if new_rev.startswith(REF_TAG_PREFIX):
            return does_tag_exist_in_remote_repo(url, new_rev, False)

        return True

    def validate_remote_repositories_state(self):
        """
        Check status of remote repositories.

        1) For Arm managed repositories - All branches/tags to be created are
        no on remote (type A)
        2) For Arm non MRRs - revision can be found on remote (type B)
        """
        self.logger.info("Validating remote repositories state...")

        """
        list of  tuples. Each tuple is of length of 2:
        index 0 : URL to check
        index 1 : revision to check
        index 2 : success indication, True for type b repository, False for
            type A.
        """
        idx_url = 0
        idx_rev = 1
        idx_success_indication = 2
        check_remote_list = []

        # add all entries from EXTERNAL_SD_KEY_NAME SD:
        for (k, v) in self.new_revisions_dict[EXTERNAL_SD_KEY_NAME].items():
            url = build_url_from_repo_name(ARM_MRR_REMOTE, k)
            check_remote_list.append((url, v[1], False))

        for file_obj in self.manifest_file_name_to_obj_dict.values():
            # file_obj is CRepoManifestFile
            for (k, v) in file_obj.repo_name_to_proj_dict.items():
                # k is a repository name and v is a matching project

                new_ref = self.get_new_ref_from_new_revision_dict(
                    file_obj.filename, k
                )

                if not new_ref:
                    continue

                url = build_url_from_repo_name(
                    file_obj.remote_key_to_remote_dict[v.remote_key],
                    v.full_name,
                )
                check_remote_list.append((url, new_ref, not v.is_arm_mrr))

        self.logger.debug("===check_remote_list:")
        self.logger.debug(pformat(check_remote_list))

        # check concurrently that none of the repositories in mrr_url_set
        # has a branch called 'create_branch_name'
        self.logger.info(
            "Starting %d concurrent threads to validate "
            "remote repositories state..." % len(check_remote_list)
        )
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=len(check_remote_list)
        ) as executor:

            future_to_git_url = {
                executor.submit(
                    self.validate_remote_repositories_state_helper,
                    worker_input[idx_url],
                    worker_input[idx_rev],
                ): worker_input
                for worker_input in check_remote_list
            }

            for future in concurrent.futures.as_completed(
                future_to_git_url, MAX_TMO_SEC
            ):
                worker_input = future_to_git_url[future]
                result = future.result()
                if result != worker_input[idx_success_indication]:
                    raise argparse.ArgumentTypeError(
                        "revision {} {} exist on remote url {}".format(
                            worker_input[idx_rev],
                            "does not"
                            if worker_input[idx_success_indication]
                            else "",
                            worker_input[idx_url],
                        )
                    )

        self.logger.info("Worker threads done...")

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
        Validate correct logical dependencies between manifest and input files.

        Check that :
        1. All file-specific SDs point to actual files
        2. All repository names in SDs points to at least one actual project
            in manifest files if they are in sd name COMMON_SD_KEY_NAME
            (case B), or if the sd is file specific it must point to a project
            which can be found in that file (case A)
        """
        self.logger.info(
            "Validating cross dependencies (input file vs manifest files)..."
        )

        for file_name, sd in self.new_revisions_dict.items():
            if file_name == EXTERNAL_SD_KEY_NAME:
                continue

            # checking 1
            _dict = self.external_repo_name_to_cloned_repo_dict[
                MBL_MANIFEST_REPO_NAME
            ]
            if file_name != COMMON_SD_KEY_NAME:
                found = file_name in self.manifest_file_name_to_obj_dict
                if not found:
                    mbl_manifest_path = _dict.clone_dest_path
                    raise ValueError(
                        "main entry key {} in user input file "
                        "is not found in {}".format(
                            file_name,
                            os.path.join(
                                mbl_manifest_path, file_name + ".xml"
                            ),
                        )
                    )

            # checking 2
            for repo_name in sd:
                found = False
                if file_name != COMMON_SD_KEY_NAME:
                    found = (
                        repo_name
                        in self.manifest_file_name_to_obj_dict[
                            file_name
                        ].repo_name_to_proj_dict
                    )
                else:
                    for f in self.manifest_file_name_to_obj_dict.values():
                        if repo_name in f.repo_name_to_proj_dict:
                            found = True
                            break
                if not found:
                    raise ValueError(
                        "invalid input file :"
                        " entry ({}, {}) not found!".format(
                            file_name, repo_name
                        )
                    )

        self.validate_remote_repositories_state()

    def parse_and_validate_input_file(self):
        """..."""
        self.logger.info(
            "Parsing and validating input file %s..."
            % self.args.refs_input_file_path
        )

        # Open the given input and parse into new_revision_dict dictionary,
        # detect duplicate main key
        with open(
            self.args.refs_input_file_path, encoding="utf-8"
        ) as data_file:
            try:
                nrd = json.loads(
                    data_file.read(),
                    object_pairs_hook=self.dict_raise_on_duplicates,
                )
            except json.decoder.JSONDecodeError as err:
                self.logger.info("Illegal json file!", err)
                sys.exit(-1)

        """
        Check that exist at least EXTERNAL_SD_KEY_NAME key with a
        sub-dictionary that comply with :
        1. All pairs are (key, lists of length 2), and the value list must
        have distinct values.
        2. armmbed/mbl-manifest repository exist in sub-dictionary
        """
        if EXTERNAL_SD_KEY_NAME not in nrd:
            raise ValueError(
                "main entry key %s could not be found in user input file"
                % EXTERNAL_SD_KEY_NAME
            )
        if MBL_MANIFEST_REPO_NAME not in nrd[EXTERNAL_SD_KEY_NAME]:

            raise ValueError(
                "%s key could not be found in user input "
                "file under %s"
                % (MBL_MANIFEST_REPO_NAME, EXTERNAL_SD_KEY_NAME)
            )

        for l in nrd[EXTERNAL_SD_KEY_NAME].values():
            if len(l) != 2:
                raise ValueError(
                    "Bad length for list %s - All lists under key %s in user "
                    "input file must be of length 2!"
                    % (l, EXTERNAL_SD_KEY_NAME)
                )

            if l[0] == l[1]:
                raise ValueError(
                    "Bad list %s - non-distinct values under "
                    "key %s in user input file!" % (l, EXTERNAL_SD_KEY_NAME)
                )

        # set the clone ref for mbl-manifest
        self.mbl_manifest_clone_ref = nrd[EXTERNAL_SD_KEY_NAME][
            MBL_MANIFEST_REPO_NAME
        ][0]

        """
        do not allow any repo name under common SD to appear in any other SD
        pair as key do not allow any repo name under external SD to appear in
        any other SD pair as key l carry a merged list of all pairs which are
        not in common/external SDs
        """
        validation_list = []
        for (key, val) in nrd.items():
            if (key != COMMON_SD_KEY_NAME) and (key != EXTERNAL_SD_KEY_NAME):
                validation_list += val
        if validation_list:
            if COMMON_SD_KEY_NAME in nrd:
                for key in nrd[COMMON_SD_KEY_NAME].keys():
                    if key in validation_list:
                        raise ValueError(
                            "Invalid input in file {} : key {} "
                            "found in {} but also in other file "
                            "specific file SDs!".format(
                                self.args.refs_input_file_path,
                                key,
                                COMMON_SD_KEY_NAME,
                            )
                        )

            if EXTERNAL_SD_KEY_NAME in nrd:
                for key in nrd[EXTERNAL_SD_KEY_NAME].keys():
                    if key in validation_list:
                        raise ValueError(
                            "Invalid input in file {} : key {} found in {}, "
                            "but also in other file specific file SDs!".format(
                                self.args.refs_input_file_path,
                                key,
                                EXTERNAL_SD_KEY_NAME,
                            )
                        )

        # # do not allow for the same repo name in file specific SD to have the
        # # same branch name, or the same tag name (equal tag and branch name
        # # in separate repos is allowed, but not recommended!)
        # tup_list = []
        # for (sd_name, sd) in nrd.items():
        #     if sd_name in [EXTERNAL_SD_KEY_NAME, COMMON_SD_KEY_NAME]:
        #         continue
        #     tup_list += [(v, k) for k, v in sd.items()]
        # for t in tup_list:
        #     if tup_list.count(t) > 1:
        #         raise ValueError(
        #             "Invalid input file %s : The pair %s appears in more "
        #             "than one file specific SD! (put in %s?)"
        #             % (self.args.refs_input_file_path, t, COMMON_SD_KEY_NAME)
        #         )

        self.new_revisions_dict = nrd

    def get_new_ref_from_new_revision_dict(self, sd_key_name, repo_name):
        """..."""
        if (sd_key_name in self.new_revisions_dict) and (
            repo_name in self.new_revisions_dict[sd_key_name]
        ):

            if sd_key_name == EXTERNAL_SD_KEY_NAME:
                return self.new_revisions_dict[sd_key_name][repo_name][1]
            return self.new_revisions_dict[sd_key_name][repo_name]

        if (
            COMMON_SD_KEY_NAME in self.new_revisions_dict
            and repo_name in self.new_revisions_dict[COMMON_SD_KEY_NAME]
        ):
            return self.new_revisions_dict[COMMON_SD_KEY_NAME][repo_name]

        return None

    def create_and_update_new_revisions_worker(
        self,
        remote,
        name_prefix,
        short_name,
        clone_base_path,
        cur_rev,
        new_rev,
    ):
        """create_and_update_new_revisions_worker."""
        repo = CGitClonedRepository(
            remote, name_prefix, short_name, clone_base_path, cur_rev
        )

        new_rev_short = new_rev.rsplit("/", 1)[1]

        if not repo.handle.head.is_detached:
            src_cmt_ref = repo.handle.active_branch.commit
        else:
            src_cmt_ref = repo.handle.head.commit

        # Create the new branch/tag
        if new_rev.startswith(REF_BRANCH_PREFIX):
            new_branch = repo.handle.create_head(new_rev_short)
            assert new_branch.commit == src_cmt_ref
            new_branch.checkout()
            new_rev = new_branch

            summary_log_list.append(
                SUMMARY_H_BRANCH
                + "Created and checkout new branch %s from  %s "
                "on repository % s"
                % (new_rev_short, src_cmt_ref.hexsha, repo.full_name)
            )
        else:
            new_tag = repo.handle.create_tag(new_rev_short, ref=src_cmt_ref)
            assert new_tag.commit == src_cmt_ref
            assert new_tag.tag is None
            new_rev = new_tag

            summary_log_list.append(
                SUMMARY_H_TAG
                + "Created and checkout new tag %s on commit %s on "
                "repository % s"
                % (new_rev_short, src_cmt_ref.hexsha, repo.full_name)
            )

        if repo.full_name not in [
            MBL_MANIFEST_REPO_NAME,
            MBL_LINKED_REPOSITORIES_REPO_NAME,
        ]:
            if self.diag_repo_push(repo):
                self.repo_push(repo, new_rev)
                summary_log_list.append(
                    SUMMARY_H_PUSH
                    + "Pushed from repository clone path={} a new branch={} "
                    "to remote url={}".format(
                        repo.clone_dest_path,
                        repo.handle.active_branch.name,
                        repo.url,
                    )
                )
            else:
                self.logger.info("Skip pushing...")

        return repo

    def update_mbl_linked_repositories_conf_helper(self, git_repo):
        """Worker function. Update mbl-linked-repositories.conf file.."""
        if not git_repo:
            return

        self.logger.info(
            "Start updating file %s in repository %s (if needed)"
            % (
                MBL_LINKED_REPOSITORIES_REPO_PATH,
                MBL_LINKED_REPOSITORIES_REPO_NAME,
            )
        )

        # check if file exist
        file_path = os.path.join(
            git_repo.clone_dest_path, MBL_LINKED_REPOSITORIES_REPO_PATH
        )
        if not os.path.exists(file_path):
            raise FileNotFoundError("File %s not found!" % file_path)

        # Create backup
        self.logger.info(
            "Created backup file %s from %s"
            % (file_path + FILE_BACKUP_SUFFIX, file_path)
        )
        summary_log_list.append(
            SUMMARY_H_BKP
            + "Created back file %s from %s"
            % (file_path + FILE_BACKUP_SUFFIX, file_path)
        )
        copyfile(file_path, file_path + FILE_BACKUP_SUFFIX)

        """
        Open the file, traverse all over the EXTERNAL_SD_KEY_NAME SD
        repositories, and replace We expect file structure, where each element
        represents a linked repository has 3 settings :
        1) options
        2) repo URL
        3) SRCREV in that order
            We are going to locate the repo name and change the SRCREV
        """
        is_changed = False
        d = self.external_repo_name_to_cloned_repo_dict
        for repo_name in self.new_revisions_dict[EXTERNAL_SD_KEY_NAME].keys():
            if repo_name not in [
                MBL_MANIFEST_REPO_NAME,
                MBL_LINKED_REPOSITORIES_REPO_NAME,
            ]:

                with in_place.InPlace(file_path) as file:
                    next_line_replace = False
                    for line in file:
                        if (
                            line.lower().find("git@github.com/" + repo_name)
                            != -1
                        ):
                            active_branch = d[repo_name].handle.active_branch
                            commit_hash = active_branch.commit
                            branch_name = active_branch.name

                            if line.find(";branch=") != -1:
                                # match text between two quotes
                                matches = re.findall(r";branch=(.+?);", line)
                                for m in matches:
                                    if m != branch_name:
                                        line = line.replace(
                                            ";%s;" % m,
                                            ";branch=%s;" % branch_name,
                                        )
                                        is_changed = True

                            # TODO : replace former line or reformat file..
                            next_line_replace = True
                        elif next_line_replace:
                            if (
                                line.find('"') == line.rfind('"')
                                or line.count('"') != 2
                            ):
                                raise SyntaxError(
                                    "Bad format for file [{}] "
                                    "in line [{}]".format(file_path, line)
                                )

                            # match text between two quotes
                            matches = re.findall(r"\"(.+?)\"", line)
                            for m in matches:
                                if m != commit_hash.hexsha:
                                    line = line.replace(
                                        '"%s"' % m, '"%s"' % commit_hash
                                    )
                                    is_changed = True
                            next_line_replace = False
                        file.write(line)

        if is_changed:
            ret_list = git_repo.handle.index.add([file_path], write=True)
            assert len(ret_list) == 1
            git_repo.handle.index.commit(
                "%s Automatic Commit Message" % program_name
            )
            self.logger.info(
                "File %s has been modified and committed" % file_path
            )
            summary_log_list.append(
                SUMMARY_H_MODIFY_FILE
                + "File %s has been modified and committed on repository %s"
                % (file_path, git_repo.full_name)
            )

        if self.diag_repo_push(git_repo):
            self.repo_push(git_repo, git_repo.handle.active_branch)
            summary_log_list.append(
                SUMMARY_H_PUSH
                + "Pushed from repository clone path={} a new branch={} "
                "to remote url={},"
                "\nNew commit hash={}".format(
                    git_repo.clone_dest_path,
                    git_repo.handle.active_branch.name,
                    git_repo.url,
                    git_repo.handle.active_branch.commit.hexsha,
                )
            )
        else:
            self.logger.info("Skip pushing...")

    def update_mbl_linked_repositories_conf(self):
        """update_mbl_linked_repositories_conf."""
        # update all MBL_LINKED_REPOSITORIES_REPO_NAME repositories
        d = self.external_repo_name_to_cloned_repo_dict
        if MBL_LINKED_REPOSITORIES_REPO_NAME in d:
            self.update_mbl_linked_repositories_conf_helper(
                d[MBL_LINKED_REPOSITORIES_REPO_NAME]
            )
        for file_obj in self.manifest_file_name_to_obj_dict.values():
            if (
                MBL_LINKED_REPOSITORIES_REPO_NAME
                in file_obj.repo_name_to_proj_dict
            ):
                self.update_mbl_linked_repositories_conf_helper(
                    file_obj.repo_name_to_proj_dict[
                        MBL_LINKED_REPOSITORIES_REPO_NAME
                    ].cloned_repo
                )

    def diag_repo_push(self, repo):
        """
        Diagnostic mode - before pushing.

        Return True if program should push.
        """
        if self.args.diagnostic_mode:
            print("\n=============================")
            print("Diagnostic Mode - BEFORE PUSH TO REMOTE")
            print("New branch : %s" % repo.handle.active_branch.name)
            if repo.full_name in [
                MBL_MANIFEST_REPO_NAME,
                MBL_LINKED_REPOSITORIES_REPO_NAME,
            ]:
                print(
                    "New Commit SHA : %s"
                    % repo.handle.active_branch.commit.hexsha
                )

            print("Remote URL : %s" % repo.url)
            print("Repository clone path : %s" % repo.clone_dest_path)
            answer = input(
                "Press n/N to continue without pushing, "
                "q/Q to quit, "
                "or any other key to continue : "
            )

            if answer.lower() == "q":
                sys.exit(0)
            if answer.lower() == "n":
                return False
        return True

    def mbl_manifest_repo_push(self):
        """Push MBL_MANIFEST_REPO_NAME repo to remote."""
        repo = self.external_repo_name_to_cloned_repo_dict[
            MBL_MANIFEST_REPO_NAME
        ]
        repo.handle.git.add(update=True)
        repo.handle.index.commit("release manager automatic commit")

        if self.diag_repo_push(repo):
            self.repo_push(repo, repo.handle.active_branch)
            summary_log_list.append(
                SUMMARY_H_PUSH + "Pushed from repository clone path={} a new "
                "branch={} to remote url={},"
                "\nNew commit hash={}".format(
                    repo.clone_dest_path,
                    repo.handle.active_branch.name,
                    repo.url,
                    repo.handle.active_branch.commit.hexsha,
                )
            )
        else:
            self.logger.info("Skip pushing...")

    def clone_and_create_new_revisions(self):
        """
        Clone all external and Arm MRR repositories.

        Concurrently, checkout current revision.
        """
        self.logger.info("Cloning and creating new revisions...")

        # list of tuples
        clone_tup_list = []
        # clone all external repositories under self.tmp_dir_path
        for (main_key, sd) in self.new_revisions_dict.items():
            for (key, rev) in sd.items():
                if main_key == EXTERNAL_SD_KEY_NAME:
                    if key != MBL_MANIFEST_REPO_NAME:
                        prefix, name = key.rsplit("/", 1)
                        clone_tup_list.append(
                            # tuple
                            (
                                key,
                                ARM_MRR_REMOTE,
                                prefix,
                                name,
                                self.tmp_dir_path,
                                rev[0],
                                rev[1],
                                main_key,
                            )
                        )

        """
        Clone all Arm MRRs, each one on a sub-folder belong to the file.

        For example, for default.xml, all matching repos will be cloned
        under <self.tmp_dir_path>/default
        """
        for file_obj in self.manifest_file_name_to_obj_dict.values():
            for (name, proj) in file_obj.repo_name_to_proj_dict.items():
                new_ref = self.get_new_ref_from_new_revision_dict(
                    file_obj.filename, proj.full_name
                )
                if proj.is_arm_mrr and new_ref:
                    prefix, name = proj.full_name.rsplit("/", 1)

                    clone_tup_list.append(
                        # tuple
                        (
                            proj.full_name,
                            file_obj.remote_key_to_remote_dict[
                                proj.remote_key
                            ],
                            prefix,
                            name,
                            os.path.join(self.tmp_dir_path, file_obj.filename),
                            proj.revision,
                            new_ref,
                            file_obj.filename,
                        )
                    )

        self.logger.debug("=== clone_tup_list:")
        self.logger.debug(pformat(clone_tup_list))

        self.logger.info(
            "Starting %d concurrent threads to clone repositories..."
            % len(clone_tup_list)
        )
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=len(clone_tup_list)
        ) as executor:

            future_to_git_url = {
                executor.submit(
                    self.create_and_update_new_revisions_worker,
                    worker_input[1],
                    worker_input[2],
                    worker_input[3],
                    worker_input[4],
                    worker_input[5],
                    worker_input[6],
                ): worker_input
                for worker_input in clone_tup_list
            }

            for future in concurrent.futures.as_completed(
                future_to_git_url, MAX_TMO_SEC
            ):

                worker_input = future_to_git_url[future]
                result = future.result()
                if not result:
                    raise argparse.ArgumentTypeError(
                        "revision {} exist on remote url {}".format(
                            worker_input[1], worker_input[0]
                        )
                    )
                else:
                    if worker_input[7] == EXTERNAL_SD_KEY_NAME:
                        self.external_repo_name_to_cloned_repo_dict[
                            worker_input[0]
                        ] = result
                    else:
                        odict = self.manifest_file_name_to_obj_dict[
                            worker_input[7]
                        ]
                        pdict = odict.repo_name_to_proj_dict[worker_input[0]]
                        pdict.cloned_repo = result
        self.logger.info("Worker threads done...")

    def print_summary(self):
        """Print summary in different formatting."""
        handler = self.logger.root.handlers[0]
        handler.setFormatter(logging.Formatter(LOGGING_SUMMARY_FORMAT))

        self.logger.info("\n\n")
        self.logger.info("===============================================")
        self.logger.info("=== === === === === SUCCESS === === === === ===")
        self.logger.info("===============================================\n")

        if not self.args.remove_temporary_folder:
            self.logger.info("Temporary folder: %s" % self.tmp_dir_path)
        self.logger.info(
            "Time running: %s" % int(time.time() - self.start_time)
        )

        self.logger.info("\n== Event log ==\n")
        for (idx, record) in enumerate(summary_log_list):
            self.logger.info("{}. {}".format(idx + 1, record))
            self.logger.info("-----")

        handler.setFormatter(logging.Formatter(LOGGING_REGULAR_FORMAT))

    class StoreValidFile(argparse.Action):
        """
        parser helper class.

        Costume action - check that the given file path exist on local host.
        """

        def __call__(self, parser, namespace, values, option_string=None):
            """Function call operator."""
            file_path = os.path.abspath(values)
            if not os.path.isfile(file_path):
                raise argparse.ArgumentTypeError(
                    "The path %s does not exist!" % file_path
                )
            filename, file_extension = os.path.splitext(
                os.path.basename(file_path)
            )
            if not file_extension == ".json":
                raise argparse.ArgumentTypeError(
                    "File %s does not end with '.json' prefix!" % file_path
                )
            setattr(namespace, self.dest, file_path)

    def get_argument_parser(self):
        """Define and parse script input arguments."""
        parser = argparse.ArgumentParser(
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            description=program_name + " script",
        )

        parser.add_argument(
            "refs_input_file_path",
            action=self.StoreValidFile,
            help="path to update.json file which holds a dictionary of pairs "
            "(repository name, branch / tag / hash)."
            "For more information and exact format "
            "see mbl-tools/build-mbl/README.md.",
        )

        parser.add_argument(
            "-v",
            "--verbose",
            help="verbose logging - prints all logs",
            action="store_true",
        )

        parser.add_argument(
            "-d",
            "--diagnostic_mode",
            help="diagnostic mode - prompts before each significant step, "
            "allowing user to check changes in files and repositories",
            action="store_true",
        )

        parser.add_argument(
            "-s",
            "--simulate",
            help="do not push to remote, everything else will be executed "
            "exactly the same but nothing is actually pushed into "
            "remote.",
            action="store_true",
        )

        parser.add_argument(
            "-r",
            "--remove_temporary_folder",
            help="On competition, remove the temporary folder and all of its "
            "content",
            action="store_true",
        )

        return parser
