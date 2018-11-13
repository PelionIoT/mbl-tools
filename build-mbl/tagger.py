#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

#TODO - add to explenation
#https://wiki.yoctoproject.org/wiki/Stable_branch_maintenance
'''
Arm MRRs	Arm owned Manifest Referenced Repositories
Non-Arm MRRs	Community (or Linaro) owned Manifest Referenced Repositories
MRR	Manifest Referenced Repository - a repository referenced in a repo manifest file (in the mbl-manifest repo)
'''

"""Part of mbl-tools. 
Tag new development and release branches on all manifest files and internally linkes repositories."""
from git import Repo
import xml.etree.ElementTree as ET
import os, glob, git, sys, logging, argparse, tempfile, concurrent.futures

#TODO - change name??
module_name = "ReleaseManager"
__version__ = "1.0.0"

# constants
MAX_TMO_SEC = 20
MRR_MANIFEST_REMOTE_KEY = "github"
MRR_URL_PREFIX = "armmbed"
MRR_URL_PATTERN = "ssh://git@github.com:/{}/{}.git"
MBL_MANIFEST_REPO_BASE_NAME = "mbl-manifest"
MBL_MANIFEST_REPO_URL = MRR_URL_PATTERN.format(MRR_URL_PREFIX, MBL_MANIFEST_REPO_BASE_NAME)
YOCTO_STABLE_BRANCHNAME_TO_BITBAKEVER_DICT = { # This dictionary must be maintained 
    "thud" : "1.40",
    "sumo" : "1.38",
    "rocko" : "1.36",
    "pyro" : "1.34",
    "morty" : "1.32",
    "krogoth" : "1.30",
    "jethro" : "1.28",
    "fido" : "1.26",
    "dizzy" : "1.24",
    "daisy" : "1.22",
    "dora" : "1.20",
    "dylan" : "1.18",
    "danny" : "1.16"  
}

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
    refs = lsremote(repo_url) 
    if 'refs/heads/' + branch_name in refs: 
        return True 
    return False

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
#   RepoManifestFile Class
#
########################################################################
class RepoManifestFile(object):
    def __init__(self, fn, tree, root, default_rev, 
                 remote_name_to_fetch_prefix_dict, base_name_to_proj_dict):            
        #file name
        self.file_name = fn
        # entire element hierarchy
        self.tree = tree
        
        # root ElementTree of file prase 
        self.root = root
        
        # default revision (branch or tag) to checkout when not specified in project
        self.default_rev = default_rev
        
        # dictionary : key is a remote name, value is a fetch prefix URL
        # This  dictionary golds all fetch URLs with a remote name as key
        self.remote_name_to_fetch_prefix_dict = remote_name_to_fetch_prefix_dict
        
        # dictionary : key is a repository base name, value is 
        # This dictionary holds all RepoManifestProject objects with repository names as key
        self.base_name_to_proj_dict = base_name_to_proj_dict
             
                
#
#   RepoManifestXml Class
#
########################################################################
class RepoManifestProject(object):
    def __init__(self, full_name, prefix, base_name, remote, url, revision):
        self.full_name = full_name
        self.prefix = prefix
        self.base_name = base_name
        self.remote = remote           
        self.url = url
        self.revision = revision
        
        # an ARM MRR must have project with :
        # remote -> MRR_MANIFEST_REMOTE_KEY = "github"
        # prefix -> MRR_URL_PREFIX = "armmbed"
        if (self.prefix == MRR_URL_PREFIX) and (self.remote == MRR_MANIFEST_REMOTE_KEY):
            self.isArmMRR = True
        else: 
            self.isArmMRR = False
#
#   GitRepository Class
#
########################################################################
class GitRepository(object):
    def __init__(self, github_prefix, base_name, clone_base_path, checkout_branch_name="master"):
        # name
        self.name = base_name
        
        # checkout branch name
        self.checkout_branch_name = checkout_branch_name
        
        # full clone path
        self.clone_path = os.path.join(clone_base_path, base_name)
        
        # repo url
        self.url = MRR_URL_PATTERN.format(github_prefix, base_name)
        
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
        self.repo_base_name_to_git_repo_dict = {}
        
        # list of RepoManifestFile objects
        self.manifest_file_list = []
                
        # set of URLs to check - build both sets to check state afterwards
        self.mrr_url_set = set()
        self.non_mrr_url_set = set()
        
        # parse arguments
        parser = self.get_argument_parser()
        self.args = parser.parse_args()
        
        # validate that 'yocto_release_codename' exist in YOCTO_STABLE_BRANCHNAME_TO_BITBAKEVER_DICT
        # from time to time youcto project will advance and script will exit with an error on new release code names
        if self.args.yocto_release_codename not in YOCTO_STABLE_BRANCHNAME_TO_BITBAKEVER_DICT:
            raise argparse.ArgumentTypeError("yocto_release_codename {} does not exist in "
            "YOCTO_STABLE_BRANCHNAME_TO_BITBAKEVER_DICT!\n(You will have to update this dictionary "
            "with the new yocto version and the matching bitbake version)".format(self.args.yocto_release_codename))
        
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
            if not is_branch_exist_in_remote_repo(MBL_MANIFEST_REPO_URL, manifest_branch_name):
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
            
            # Comment : at this stage, check only if branch name is legal.
            # We will check if branch exist on remote later on
           
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
                    url = MRR_URL_PATTERN.format(MRR_URL_PREFIX, elem)
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
            help="Name of an already exist branch on %s repository to clone from" % MBL_MANIFEST_REPO_BASE_NAME,
        )
        
        parser.add_argument(
            "-a",
            "--additional_repository_names",
            nargs='+',
            metavar="name1 name2..nameN",
            default="meta-mbl mbl-core",
            action=self.StoreAdditionalRepositoryNames, 
            help="""A list of Arm managed repository names to create a branch <create_branch_name> for. 
            Each name should be only the 'humanish' base part of the repository URL.
            For example: the name 'mbl-core' refers to URL 'git@github.com:/ARMmbed/mbl-core.git'
            Each name must not be included in the project/name value any of the manifest files in 
            mbl-manifest repository.If mbl-core is included in the list, 
            meta-mbl/conf/distro/mbl-linked-repositories.conf will be updated accordingly."""        
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
        self.repo_base_name_to_git_repo_dict[MBL_MANIFEST_REPO_BASE_NAME] = GitRepository(
            MRR_URL_PREFIX, 
            MBL_MANIFEST_REPO_BASE_NAME, 
            self.tmpdirname.name, 
            self.args.manifest_branch_name)       

        # get all files ending with .xml inside this directory. We assume they are all manifest files
        xml_file_list = []
        path = os.path.join(self.repo_base_name_to_git_repo_dict[MBL_MANIFEST_REPO_BASE_NAME].clone_path, "*.xml")
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
        #parse all xml files, create a RepoManifestFile object for each and store in manifest_file_list
        for fn in xml_file_list:            
            # get root
            tree = ET.parse(fn)
            
            #root element of the tree
            root = tree.getroot()
            
            # get default, if not found, set to master
            node = tree.find('./default')
            default_rev = "master"
            if node:
                default_rev = node.get("revision", "master")            
            
            # get remotes - store in a dictionary { name : fetch }
            remote_name_to_fetch_prefix_dict = {}
            for atype in root.findall('remote'):
                remote_name_to_fetch_prefix_dict[atype.get('name')] = atype.get('fetch')

            # get projects - store in a base project name to
            base_name_to_proj_dict = {}
            for atype in root.findall('project'):                                
                #get name and split to prefix and base name
                full_name = atype.get('name')
                prefix, base_name = full_name.rsplit('/', 1)
                if base_name in base_name_to_proj_dict:
                    raise ValueError("File %s : project %s repeats multiple times!".format(fn, base_name))
                
                #get remote and build url
                remote = atype.get('remote')                
                url = remote_name_to_fetch_prefix_dict[remote] + ":/" + full_name + ".git"
                
                #set revision
                revision = atype.get('revision')
                if not revision: revision = default_rev;
                
                #create project and insert to dictionary
                proj = RepoManifestProject(full_name, prefix, base_name, remote, url, revision)                
                base_name_to_proj_dict[base_name] = proj
            
            rmf = RepoManifestFile(fn, tree, root, default_rev, 
                                   remote_name_to_fetch_prefix_dict, base_name_to_proj_dict)
            self.manifest_file_list.append(rmf)
            
    def validate_remote_repositories_state(self):
                           
        # build dictionary from all Arm MRR, mbl-manifest and additional_repository_names
        self.mrr_url_set.add(MBL_MANIFEST_REPO_URL)
        for elem in self.args.additional_repository_names:
            self.mrr_url_set.add(MRR_URL_PATTERN.format(MRR_URL_PREFIX, elem))
            
        for f in self.manifest_file_list:
            for name, project in f.base_name_to_proj_dict.items():
                # key is the base name and v is the project object
                if project.isArmMRR:
                    self.mrr_url_set.add(project.url)
                else: 
                    self.non_mrr_url_set.add(project.url)

        # check concurrently that none of the repositories in mrr_url_set 
        # has a branch called 'create_branch_name'
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.mrr_url_set)) as executor:
            future_to_git_url = {
                executor.submit(is_branch_exist_in_remote_repo, url, self.args.create_branch_name): 
                url for url in self.mrr_url_set
            }
            for future in concurrent.futures.as_completed(future_to_git_url, MAX_TMO_SEC):
                git_url = future_to_git_url[future]                
                result = future.result()
                if result == True:
                    raise argparse.ArgumentTypeError(
                      "Branch %s found on %s" % (self.args.create_branch_name, git_url)
                    )    
        
        # check concurrently that none of the repositories in non_mrr_url_set 
        # has a branch called 'yocto_release_codename'
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.non_mrr_url_set)) as executor:
            future_to_git_url = {
                executor.submit(is_branch_exist_in_remote_repo, url, self.args.yocto_release_codename): 
                url for url in self.non_mrr_url_set
            }
            for future in concurrent.futures.as_completed(future_to_git_url, MAX_TMO_SEC):
                git_url = future_to_git_url[future]                
                result = future.result()
                if result == False:
                    raise argparse.ArgumentTypeError(
                      "Branch %s not found on %s" % (self.args.yocto_release_codename, git_url)
                    )                 
        
def _main():    
    # Create and initialize a release manager object
    rm = ReleaseManager()    
    
    # Clone the manifest repository and parse its xml files into database
    rm.parse_manifest_files()
    
    '''
    For all MRRs and additional_repository_names and mbl-manifest : check that : 'create_branch_name' does not exist
    For all non-MRRs - check that 'yocto_release_codename' branch exist
    '''
    rm.validate_remote_repositories_state()
                
    #TODO - remove
    print("dummy")
    
    
#TODO-change this later on
if __name__ == "__main__":
    sys.exit(_main())
