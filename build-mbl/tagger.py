#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

"""Part of mbl-tools. 
Tag new development and release branches on all manifest files and internally linkes repositories."""
from git import Repo
import xml.etree.ElementTree as ET
import os, glob, git, sys, logging, argparse, tempfile, concurrent.futures

#TODO - change name??
module_name = "ReleaseManager"
__version__ = "1.0.0"

# set constants
MAX_TMO = 20
MBL_MANIFEST_REPO_NAME = "mbl-manifest"
ARMMBED_GITHUB_PREFIX = "armmbed"
GITHUB_URL_PATTERN = "git@github.com:/{}/{}.git"

#
#   Global functions
#

# Returns a dictionary of remote refs
def lsremote(url):
    remote_refs = {}
    g = git.cmd.Git()
    for ref in g.ls_remote(url).split('\n'):
        hash_ref_list = ref.split('\t')
        remote_refs[hash_ref_list[1]] = hash_ref_list[0]
    return remote_refs

# Returns True if 'branch_name' exist in remote repository in URL 'repo_url'
def is_branch_exist_in_remote_repo(repo_url, branch_name):
    refs=lsremote(repo_url) 
    if 'refs/heads/' + branch_name in refs: return True; return False

# Returns True is 'branch_name' is a valid git branch name
def is_valid_git_branch_name(branch_name):
    g = git.cmd.Git()
    try:
        g.check_ref_format("--branch", branch_name)
    except git.GitCommandError:
        return False   
    return True

# Clone a repository from URL 'repo_url' into local path 'dest_full_path',
# checks out branch 'checkout_branch_name' and returns cloned repo
def clone_get_repo(dest_full_path, url, checkout_branch_name="master"):
    cloned_repo = Repo.clone_from(url, dest_full_path, branch=checkout_branch_name)
    assert cloned_repo.__class__ is Repo
    return cloned_repo

    
#
#   RepoManifestXml Class
#
########################################################################
class RepoManifestXmlDB(object):
    def __init__(self, full_name, prefix, base_name):
        self.full_name = full_name
        self.prefix = prefix
        self.base_name = base_name
        self.remote = ""           
        self.url = "" 
        self.revision = ""    
#
#   GitRepository Class
#
########################################################################
class GitRepository(object):
    def __init__(self, github_prefix, _base_name, clone_base_path, checkout_branch_name="master"):
        # name
        self.name = _base_name
        
        # checkout branch name
        self.checkout_branch_name = checkout_branch_name
        
        # full clone path
        self.clone_path = os.path.join(clone_base_path, _base_name)
        
        # repo url
        self.url = GITHUB_URL_PATTERN.format(github_prefix, _base_name)
        
        # clone and get git.Repo object
        self.obj_repo = clone_get_repo(self.clone_path, self.url, self.checkout_branch_name)
                            
#
#   ReleaseManager Class
#
########################################################################
class ReleaseManager(object):
    def __init__(self):
        """Initialize AppManager class."""
        
        #initialize logger  - set logging level to INFO at this initial stage
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - {%(funcName)s:%(lineno)d} - %(levelname)s \n%(message)s",
        )        
        self.logger = logging.getLogger(module_name)
        self.logger.info("Creating {} version {}".format(module_name, __version__))
                
        '''
        key : manifest file base name, without the suffix '.xml'
        value : GitRepository object
        '''
        self.repo_dict = {}
                             
        # parse arguments
        parser = self.get_argument_parser()
        self.args = parser.parse_args()
        
        # Set verbose log level if enabled by user and log command line arguments
        if self.args.verbose:
            self.logger.setLevel(logging.DEBUG)
            self.logger.debug("Command line arguments:{}".format(self.args))  
        #create a temporary folder to clone repositories in
        self.tmpdirname = tempfile.TemporaryDirectory(prefix="mbl_")
        self.logger.debug("Temporary folder: %s" % self.tmpdirname.name) 
                

    # Costume action - check that the given manifest branch exist in mbl-manifest
    class StoreValidManifestBranchName(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            manifest_branch_name = values
            if not is_valid_git_branch_name(manifest_branch_name):
                raise argparse.ArgumentTypeError(
                  "Branch %s is invalid!" % manifest_branch_name
                )           
            mbl_manifest_git_url = GITHUB_URL_PATTERN.format(ARMMBED_GITHUB_PREFIX, MBL_MANIFEST_REPO_NAME)
            if not is_branch_exist_in_remote_repo(mbl_manifest_git_url, manifest_branch_name):
                raise argparse.ArgumentTypeError(
                  "Branch %s not found on %s" % (manifest_branch_name, mbl_manifest_url)
              )                            
            setattr(namespace, self.dest, manifest_branch_name)
        
     # Costume action - check that the given create branch name does not exist in mbl-manifest 
     # or any of the arm_mrr_dict key repositories
    class StoreValidCreateBranchName(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            create_branch_name = values
            if not is_valid_git_branch_name(create_branch_name):
                raise argparse.ArgumentTypeError("Branch %s is invalid!" % create_branch_name) 
            
            '''
             git_url_list = [ mbl_manifest_url ]
                     
             for url in arm_mrr_dict.values():
                 git_url_list.append(url)
                     
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
            '''                            
            setattr(namespace, self.dest, create_branch_name)
       
    # Costume action - check that the given yocto release is valid.
    # At this stage script check that string consists of alphabetic characters only.
    # TODO : parse release names from: https://wiki.yoctoproject.org/wiki/Releases and check that name 
    # is one of  the code names
    class StoreValidYoctoReleaseName(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            yocto_release_codename = values        
            if not yocto_release_codename.isalpha():
                raise argparse.ArgumentTypeError(
                  "yocto_release_codename %s must consists of alphabetic characters only " % (yocto_release_codename)
                )                    
                                        
            setattr(namespace, self.dest, yocto_release_codename)
    
    #TODO    
    class StoreAdditionalRepositoryNames(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            repo_list = values
            for elem in repo_list:                       
                try:   
                    url = GITHUB_URL_PATTERN.format(ARMMBED_GITHUB_PREFIX, elem)
                    refs=lsremote(url)
                    if not refs:
                        raise argparse.ArgumentTypeError(
                          "additional_repository_names: the repository url %s does not exist!" % url
                        )                          
                except git.GitCommandError:
                    raise argparse.ArgumentTypeError(
                        "additional_repository_names: the repository %s url does not exist!" % url
                        )
            setattr(namespace, self.dest, values)
         
             
    def get_argument_parser(self):
        parser = argparse.ArgumentParser(
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            description=module_name + " script",
        )
                    
        parser.add_argument(
            "create_branch_name",
            action=self.StoreValidCreateBranchName,
            help="Name of branch to be created across all internally linked repository repositories and Arm-MRRs"
        )
        
        parser.add_argument(
            "yocto_release_codename",
            action=self.StoreValidYoctoReleaseName,
            help="Name of yocto release codename (see https://wiki.yoctoproject.org/wiki/Releases)",
        )
    
        parser.add_argument(
            "-m",
            "--manifest_branch_name",
            metavar="",
            action=self.StoreValidManifestBranchName, 
            default="master",
            help="Name of an already exist branch on %s repository to clone from" % MBL_MANIFEST_REPO_NAME,
        )
        
        parser.add_argument(
            "-a",
            "--additional_repository_names",
            nargs='+',
            metavar="name1 name2..nameN",
            default="meta-mbl mbl-core",
            action=self.StoreAdditionalRepositoryNames, 
            help="""A list of Arm managed repository names to create a branch <create_branch_name> for. 
            Each name should be only the "humanish" base part of the repository URL.
            For example: the name 'mbl-core' will point to 'git@github.com:ARMmbed/mbl-core.git'
            Each name must not be included in any of the manifest files in mbl-manifest repository.
            If mbl-core is included in the list, meta-mbl/conf/distro/mbl-linked-repositories.conf will be updated accordingly."""        
        )
        
        parser.add_argument(
            "-v",
            "--verbose",
            help="increase output verbosity",
            action="store_true",
        )
        
        return parser
    
    def parse_manifest_files(self):
        ## clone mbl-manifest repository first and checkout manifest_branch_name
        self.repo_dict[MBL_MANIFEST_REPO_NAME] = GitRepository(
            ARMMBED_GITHUB_PREFIX, MBL_MANIFEST_REPO_NAME, self.tmpdirname.name, self.args.manifest_branch_name)       

        # get all files ending with .xml inside this directory. We assume they are all manifest files
        xml_file_list = []
        path = os.path.join(self.repo_dict[MBL_MANIFEST_REPO_NAME].clone_path, "*.xml")
        for file_name in glob.glob(path):
            xml_file_list.append(os.path.abspath(file_name))
        
        '''
        We are interested in 3 subelements types : 
        1. 'default' : defult fetch attributes. Types:
            a. 'revision' - default revision in case that revision=None in project definition
        2. 'remote' : remote repository UTL attributes
            a. 'fetch' - base fetch URL (prefix)
            b. 'name' - this name is the key to the matching fetch attribute
        3. 'project' - each project describes an MRR. Types:
            a. 'name' - repository prefix concatenated with the repository base name
            b. 'remote' - 2.b name - should be replace with fetch in order to fetch the repository
            c. 'revision' - this one is optional tag or branch (head) name. If not exist, assign revision from 1.a
        '''        
        #parse all xml files, create a XXXXXXXXXXXXXXXX object for each and store in XXXXX
        for fn in xml_file_list:
            # get root
            tree = ET.parse(fn)
            root = tree.getroot()
            
            # get default
            node = tree.find('./default')
            default_rev = node.get('revision')            
            if not default_rev: default_rev = "master";
            
            # get remotes - store in a dictionary { name : fetch }
            name_to_fetch_dict = {}
            for atype in root.findall('remote'):
                name_to_fetch_dict[atype.get('name')] = atype.get('fetch')

            # get projects - store in a base project name to
            name_to_proj_dict = {}
            for atype in root.findall('project'):                                
                #get name and split to prefix and base name
                full_name = atype.get('name')
                prefix, base_name = full_name.rsplit('/', 1)
                if base_name in name_to_proj_dict:
                    raise ValueError("File %s : project %s repeats multiple times!".format(fn, base_name))
                proj = RepoManifestXmlDB(full_name, prefix, base_name)
                
                #get remote and build url
                proj.remote = atype.get('remote')                
                proj.url = name_to_fetch_dict[proj.remote] + ":/" + proj.full_name + ".git"
                
                #set revision
                proj.revision = atype.get('revision')
                if not proj.revision: proj.revision = default_rev;
                name_to_fetch_dict[base_name] = proj
            
            todo - store in XXXXX 
                                            
def _main():    
    #create and initialize a release manager object
    rm = ReleaseManager()    
    
    #clone the manifest repository and parse its xml files to build MRR list
    rm.parse_manifest_files()
    
    #TODO - remove
    print("dummy")
    
    
#TODO-change this later on
if __name__ == "__main__":
    sys.exit(_main())
