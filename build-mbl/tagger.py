#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

"""Part of mbl-tools. 
Tag new development and release branches on all manifest files and internally linkes repositories."""

import argparse
import logging
import sys
import git
import os
import concurrent.futures

#TODO - change name
module_name="tagger"
max_tmo=20

mbl_manifest_repo_name = "mbl-manifest"
mbl_manifest_url = "git@github.com:armmbed/%s.git" % mbl_manifest_repo_name
mbl_mrr_git_pattern = "git@github.com:%s.git"


arm_mrr_list =  [
                    "armmbed/mbl-config",
                    "armmbed/meta-mbl-internal-extras",
                    "armmbed/meta-mbl-reference-apps",
                    "armmbed/meta-mbl-reference-apps-internal", 
                    "armmbed/meta-mbl"                    
                ]
none_arm_mrr_list = [
                        "Freescale/meta-freescale-3rdparty",
                        "git/meta-freescale",
                        "git/meta-raspberrypi",
                        "git/meta-virtualization", 
                        "openembedded/bitbake", 
                        "openembedded/meta-linaro", 
                        "openembedded/meta-openembedded", 
                        "openembedded/openembedded-core"                    
]

# Return a dictionary of rempote refs
def lsremote(url):
    remote_refs = {}
    g = git.cmd.Git()
    for ref in g.ls_remote(url).split('\n'):
        hash_ref_list = ref.split('\t')
        remote_refs[hash_ref_list[1]] = hash_ref_list[0]
    return remote_refs
    
def is_branch_exist_in_remote_repo(repo_url, branch_name):
    refs=lsremote(repo_url) 
    if 'refs/heads/' + branch_name in refs: return True; return False
                
# Costume action - check that the given manifest branch exist in mbl-manifest
class StoreValidManifestBranchName(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        manifest_branch_name = values
        if not is_branch_exist_in_remote_repo(mbl_manifest_url, manifest_branch_name):
            raise argparse.ArgumentTypeError(
              "Branch %s not found on %s" % (manifest_branch_name, mbl_manifest_url)
          )                            
        setattr(namespace, self.dest, manifest_branch_name)
   

# Costume action - check that the given create branch name does not exist in mbl-manifest 
# or any of the arm_mrr_list repositories
class StoreValidCreateBranchName(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        create_branch_name = values        
        git_url_list = [ mbl_manifest_url ]
                
        for e in arm_mrr_list:
            git_url_list.append(mbl_mrr_git_pattern % e)
        
        # check that non of the repositories in 'list' has a branch called 'create_branch_name'
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(git_url_list)) as executor:
            future_to_git_url = {
                executor.submit(is_branch_exist_in_remote_repo, url, create_branch_name): 
                url for url in git_url_list
            }
            for future in concurrent.futures.as_completed(future_to_git_url, max_tmo):
                git_url = future_to_git_url[future]                
                result = future.result()
                if result:
                    raise argparse.ArgumentTypeError(
                      "Branch %s found on %s" % (create_branch_name, git_url)
                    )                    
                                    
        setattr(namespace, self.dest, create_branch_name)
        
def get_argument_parser():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description=module_name + " script",
    )
        
    parser.add_argument(
        "create_branch_name",
        action=StoreValidCreateBranchName,
        help="Name of branch to be created across all internally linked repository repositories and Arm-MRRs"
    )
    
    parser.add_argument(
        "yocto_release_codename",
        help="Name of yocto release codename (see https://wiki.yoctoproject.org/wiki/Releases)",
    )

    parser.add_argument(
        "-m",
        "--manifest_branch_name",
        metavar="",
        action=StoreValidManifestBranchName, 
        default="master",
        help="Name of an already exist branch on %s repository to clone from" % mbl_manifest_repo_name,
    )
    
    parser.add_argument(
        "-v",
        "--verbose",
        help="increase output verbosity",
        action="store_true",
    )

    return parser

def _main():
    parser = get_argument_parser()
    args = parser.parse_args()
    
    info_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=info_level,
        format="%(asctime)s - %(name)s - {%(funcName)s:%(lineno)d} - %(levelname)s \n%(message)s",
    )
    logger = logging.getLogger(module_name)
    logger.debug("Command line arguments:{}".format(args))

#TODO-change this later on
if __name__ == "__main__":
    sys.exit(_main())
