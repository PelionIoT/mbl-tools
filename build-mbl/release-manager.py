#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0


'''
TODO - internal notes
add to explenation
#https://wiki.yoctoproject.org/wiki/Stable_branch_maintenance

Arm MRRs	Arm owned Manifest Referenced Repositories
Non-Arm MRRs	Community (or Linaro) owned Manifest Referenced Repositories
MRR	Manifest Referenced Repository - a repository referenced in a repo manifest file (in the mbl-manifest repo)

a revision is a commit hash or rev
'''

"""Part of mbl-tools. 
Tag new development and release branches on all manifest files and internally linkes repositories."""
import xml.etree.ElementTree as ET
import os, glob, git, sys, json, logging, argparse, tempfile, concurrent.futures, ntpath, string, re, in_place
from pprint import pprint, pformat
from shutil import copyfile
from git import Repo


#TODO - change name??
module_name = "CReleaseManager"
__version__ = "1.0.0"

# constants
INPUT_FILE_COMMON_SD_KEY_NAME = "_common_"
INPUT_FILE_ADDITIONAL_SD_KEY_NAME = "_additional_"
MAX_TMO_SEC = 120
MRR_MANIFEST_REMOTE_KEY = "github"
REF_PREFIX = "refs/"
REF_BRANCH_PREFIX = "refs/heads/"
REF_TAG_PREFIX = "refs/tags/"
HASH_FIXED_LEN = 40
INPUT_FILE_NAME = "update.json"
FILE_BACKUP_SUFFIX = "~"

# remote URL constants 
ARM_MRR_REMOTE = "ssh://git@github.com"
ARM_MRR_URL_PATTERN = "ssh://git@github.com:/{}/{}.git"
ARM_MRR_REPO_NAME_PREFIX = "armmbed"
MBL_MANIFEST_REPO_SHORT_NAME = "mbl-manifest"
MBL_MANIFEST_REPO_NAME = "{}/{}".format(ARM_MRR_REPO_NAME_PREFIX, MBL_MANIFEST_REPO_SHORT_NAME) # armmbed/mbl-manifest

# mbl-linked-repositories.conf update constants
MBL_LINKED_REPOSITORIES_REPO_NAME = "armmbed/meta-mbl"
MBL_LINKED_REPOSITORIES_REPO_PATH = "conf/distro/mbl-linked-repositories.conf"

#
#   Global functions
#

class SGlobalFuncs:
    @staticmethod
    def build_url_from_base_repo_name(remote, prefix, base_name):
        return "{}:/{}/{}.git".format(remote, prefix, base_name)

    @staticmethod
    def build_url_from_full_repo_name(remote, name):
        return "{}:/{}.git".format(remote, name)

    # Returns a dictionary of remote refs
    @staticmethod
    def lsremote(url):
        remote_refs = {}
        g = git.cmd.Git()
        for ref in g.ls_remote(url).split('\n'):
            hash_ref_list = ref.split('\t')
            remote_refs[hash_ref_list[1]] = hash_ref_list[0]
        return remote_refs


    # Returns True if 'branch_name' exist in remote repository in URL 'repo_url'
    @staticmethod
    def is_branch_exist_in_remote_repo(repo_url, branch_name, is_base_name):
        refs = SGlobalFuncs.lsremote(repo_url)
        if is_base_name:
            if 'refs/heads/' + branch_name in refs:
                return True
        if branch_name in refs:
            return True
        return False

    # Returns True if 'branch_name' exist in remote repository in URL 'repo_url'
    @staticmethod
    def is_tag_exist_in_remote_repo(repo_url, tag_name, is_base_name):
        refs = SGlobalFuncs.lsremote(repo_url)
        if is_base_name:
            if 'refs/tags/' + branch_name in refs:
                return True
        if tag_name in refs:
            return True
        return False

    @staticmethod
    def get_file_name_from_path(path, no_suffix_flag):
        ret = ntpath.basename(path)
        if (no_suffix_flag):
            tup = os.path.splitext(ret)
            ret = tup[0]
        return ret

    @staticmethod
    def get_base_rev_name(full_rev_name):
        return full_rev_name.rsplit("/", 1)[1]

    @staticmethod
    def is_valid_revision(rev):
        if not SGlobalFuncs.is_valid_git_commit_hash(rev) and \
           not SGlobalFuncs.is_valid_git_branch_name(rev) and \
           not SGlobalFuncs.is_valid_git_tag_name(rev):
            return False
        return True

    @staticmethod
    def is_valid_git_ref_name(ref):
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
        if (len(commit_hash) != 40):
            return False
        try:
            int(commit_hash, 16)
        except ValueError:
            return False
        return True

    @staticmethod
    def is_valid_git_branch_short_name(branch_name):
        g = git.cmd.Git()
        try:
            if g.check_ref_format("--branch", ref) != ref:
                raise ValueError
        except git.GitCommandError:
            return False
        except ValueError:
            return False
        return True

    # Returns True is 'branch_name' is a valid git branch name
    @staticmethod
    def is_valid_git_branch_name(branch_name):
        if not branch_name.startswith(REF_BRANCH_PREFIX):
            return False
        return SGlobalFuncs.is_valid_git_ref_name(branch_name)

    @staticmethod
    def is_valid_git_tag_name(tag_name):
        if not tag_name.startswith(REF_TAG_PREFIX):
            return False
        return SGlobalFuncs.is_valid_git_ref_name(tag_name)


    # Clone a repository from URL 'repo_url' into local path 'dest_full_path',
    # Checks out branch 'checkout_branch_name' and returns cloned repo
    @staticmethod
    def clone_repo(dest_full_path, url, checkout_rev_name="refs/heads/master"):
        is_commit_hash = False
        if (SGlobalFuncs.is_valid_git_branch_name(checkout_rev_name) and
            SGlobalFuncs.is_branch_exist_in_remote_repo(url, checkout_rev_name, False)):
            co_branch = SGlobalFuncs.get_base_rev_name(checkout_rev_name)
        elif (SGlobalFuncs.is_valid_git_tag_name(checkout_rev_name) and
            SGlobalFuncs.is_tag_exist_in_remote_repo(url, checkout_rev_name, False)):
            co_branch = SGlobalFuncs.get_base_rev_name(checkout_rev_name)
        elif SGlobalFuncs.is_valid_git_commit_hash(checkout_rev_name):
            co_branch = checkout_rev_name
            is_commit_hash = True
        else:
            raise ValueError("Invalid checkout_rev_name %s to checkout after cloning!" % checkout_rev_name)

        #create folder if not exist
        if not os.path.exists(dest_full_path):
            os.makedirs(dest_full_path)

        #now clone
        if is_commit_hash:
            cloned_repo = Repo.clone_from(url, dest_full_path)
            cloned_repo.git.checkout(co_branch)
        else:
            cloned_repo = Repo.clone_from(url, dest_full_path, branch=co_branch)
        assert cloned_repo.__class__ is Repo
        return cloned_repo


#
#   CRepoManifestFile Class
#
########################################################################
class CRepoManifestFile(object):
    def __init__(self, path, base_name, tree, root, default_rev,
                 remote_key_to_remote_dict, repo_name_to_proj_dict):

        #path + name (with no suffix)
        self.path = path
        self.base_name = base_name
                
        # entire element hierarchy
        self.tree = tree
        
        # root ElementTree of file prase 
        self.root = root
        
        # default revision (branch or tag) to checkout when not specified in project
        self.default_rev = default_rev
        
        # dictionary : key is a remote name, value is a fetch prefix URL
        # This  dictionary holds all fetch URLs with a remote name as key
        self.remote_key_to_remote_dict = remote_key_to_remote_dict
        
        # dictionary : key is a repository short name, value is 
        # This dictionary holds all CRepoManifestProject objects with repository names as key
        self.repo_name_to_proj_dict = repo_name_to_proj_dict
                             
#
#   RepoManifestXml Class
#
########################################################################
class CRepoManifestProject(object):
    def __init__(self, full_name, prefix, short_name, remote_key, url, revision):

        self.full_name = full_name
        self.name_prefix = prefix
        self.short_name = short_name
        self.remote_key = remote_key           
        self.url = url
        self.revision = revision        
        self.git_repository = None # place holder for CGitRepository object


        # an ARM MRR must have project with :
        # remote -> MRR_MANIFEST_REMOTE_KEY = "github"
        # prefix -> MRR_URL_PREFIX = "armmbed"
        if (self.name_prefix == ARM_MRR_REPO_NAME_PREFIX) and (self.remote_key == MRR_MANIFEST_REMOTE_KEY):
            self.isArmMRR = True
        else: 
            self.isArmMRR = False
#
#   CGitRepository Class
#
########################################################################
class CGitRepository(object):
    def __init__(self, remote, name_prefix, short_name, clone_base_path, checkout_rev):
        
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
        self.url = SGlobalFuncs.build_url_from_base_repo_name(remote, name_prefix, short_name)
        
        # clone and get git.Repo object
        if (self.checkout_rev.startswith(REF_BRANCH_PREFIX) or 
            self.checkout_rev.startswith(REF_TAG_PREFIX) or 
            len(self.checkout_rev) == HASH_FIXED_LEN):

            self.handle = SGlobalFuncs.clone_repo(self.clone_dest_path, self.url, self.checkout_rev)
        else:

            #try to clone as branch
            try:
                self.handle = SGlobalFuncs.clone_repo(self.clone_dest_path, self.url, REF_BRANCH_PREFIX + self.checkout_rev)
            except ValueError:
            #try to clone as tag
                self.handle = SGlobalFuncs.clone_repo(self.clone_dest_path, self.url, self.checkout_rev)
        
        logger = logging.getLogger(module_name)
        logger.info("{} created!".format(self.full_name))
                   
#
#   CReleaseManager Class
#
########################################################################
class CReleaseManager(object):
    def __init__(self):
        """Initialize AppManager class."""
        
        #initialize logger  - set logging level to INFO at this initial stage
        logging.basicConfig(
            level=logging.INFO,
            format="\n%(asctime)s - %(name)s - {%(funcName)s:%(lineno)d} - %(levelname)s \n%(message)s",
        )        
        self.logger = logging.getLogger(module_name)
        self.logger.debug("Creating {} version {}".format(module_name, __version__))
                

        # list of CRepoManifestFile objects
        self.manifest_file_name_to_obj_dict = {}


        # dictionary of CGitRepository objects. Carry only cloned repositories under INPUT_FILE_ADDITIONAL_SD_KEY_NAME section
        # other manifest git repositories are kept per project (CRepoManifestProject:git_repository object)
        # Key - repo name
        # value - cloned CGitRepository
        self.additional_repo_name_to_git_repository_dict = {}

        
        # Dictionary of dictionaries created from user input JSON file
        # Key - file name or the special keys INPUT_FILE_COMMON_SD_KEY_NAME, INPUT_FILE_ADDITIONAL_SD_KEY_NAME
        # value - a sub dictionary for this catagory. The common catagory will set the revision for all 
        # projects in all xml files while other catagories are file specific
        # Each sub-dictionary holds pairs of full repository names and a target revision to replace in XML 
        # files and (if type permits) to create branch/tag on remote
        self.new_revisions_dict = {}

        
        # list of tuples (url, rev) which have already been updated. In case of an error all remotes revisions 
        # must be deleted
        self.already_updated_remotes_list = []
        
        # parse arguments
        parser = self.get_argument_parser()
        self.args = parser.parse_args()
        
        '''delete
        # validate that 'yocto_release_codename' exist in YOCTO_STABLE_BRANCHNAME_TO_BITBAKEVER_DICT
        # from time to time youcto project will advance and script will exit with an error on new release code names
        if self.args.yocto_release_codename not in YOCTO_STABLE_BRANCHNAME_TO_BITBAKEVER_DICT:
            raise argparse.ArgumentTypeError("yocto_release_codename {} does not exist in "
            "YOCTO_STABLE_BRANCHNAME_TO_BITBAKEVER_DICT!\n(You will have to update this dictionary "
            "with the new yocto version and the matching bitbake version)".format(self.args.yocto_release_codename))
        '''
        
        # Set verbose log level if enabled by user and log command line arguments
        if self.args.verbose:
            self.logger.setLevel(logging.DEBUG)
            self.logger.debug("Command line arguments:{}".format(self.args))
            
        #create a temporary folder to clone repositories in
        self.tmpdirname = tempfile.TemporaryDirectory(prefix="mbl_")
        self.logger.debug("Temporary folder: %s" % self.tmpdirname.name)                              

    def repo_push(self, repo, new_rev):

        if self.args.simulate:
            self.logger.info("Virtually Pushing {} to {}".format(new_rev, repo.full_name))
        else:
            self.logger.info("Pushing {} to {}".format(new_rev, repo.full_name))
            repo.handle.git.push('--set-upstream', 'origin', new_rev)

    def process_manifest_files(self):
        
        # clone mbl-manifest repository first and checkout mbl_manifest_clone_ref
        self.additional_repo_name_to_git_repository_dict[MBL_MANIFEST_REPO_NAME] = self.create_and_update_new_revisions_worker(
            ARM_MRR_REMOTE,
            ARM_MRR_REPO_NAME_PREFIX, 
            MBL_MANIFEST_REPO_SHORT_NAME, 
            self.tmpdirname.name, 
            self.mbl_manifest_clone_ref,
            self.new_revisions_dict[INPUT_FILE_ADDITIONAL_SD_KEY_NAME][MBL_MANIFEST_REPO_NAME][1])

        # get all files ending with .xml inside this directory. We assume they are all manifest files
        xml_file_list = []
        path = os.path.join(
            self.additional_repo_name_to_git_repository_dict[MBL_MANIFEST_REPO_NAME].clone_dest_path,
            "*.xml")
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
            a. 'name' - repository prefix concatenated with the repository short name
            b. 'remote' - 2.b name - should be replace with fetch in order to fetch the repository
            c. 'revision' - this one is optional tag or branch (head) name. If not exist, assign revision from 1.a
        '''        
        # parse all xml files, create a CRepoManifestFile object for each and store in manifest_file_name_to_obj_dict
        for file_path in xml_file_list:            
            # get root
            tree = ET.parse(file_path)
            
            # root element of the tree
            root = tree.getroot()
            
            # get default, if not found, set to master
            node = tree.find('./default')
            default_rev = "master"
            if node:
                default_rev = node.get("revision", "master")            
            
            # get remotes - store in a dictionary { remote key : remote URL prefix }
            remote_key_to_remote_dict = {}
            for atype in root.findall('remote'):
                remote_key_to_remote_dict[atype.get('name')] = atype.get('fetch')

            # get projects - store in a short project name to
            name_to_proj_dict = {}
            for atype in root.findall('project'):                                
                # get name and split to prefix and short name
                full_name = atype.get('name')
                prefix, short_name = full_name.rsplit('/', 1)
                if short_name in name_to_proj_dict:
                    raise ValueError("File %s : project %s repeats multiple times!".format(file_path, short_name))
                
                #get remote key and build url
                remote_key = atype.get('remote')                
                url = remote_key_to_remote_dict[remote_key] + ":/" + full_name + ".git"
                
                # get and set new revision
                revision = atype.get('revision')
                if not revision:
                    revision = default_rev

                base_name = SGlobalFuncs.get_file_name_from_path(file_path, True)

                # create project and insert to dictionary
                proj = CRepoManifestProject(full_name, prefix, short_name, remote_key, url, revision)
                name_to_proj_dict[full_name] = proj

                # set the new revision, that will save time, we are already in the place we want to change!
                new_ref = self.get_new_ref_from_new_revision_dict(base_name, full_name)
                if new_ref == REF_BRANCH_PREFIX +  default_rev:
                    del atype.attrib["revision"]
                else:
                    if new_ref:
                        atype.set('revision', SGlobalFuncs.get_base_rev_name(new_ref))

            rmf = CRepoManifestFile(file_path, base_name, tree, root, default_rev,
                                   remote_key_to_remote_dict, name_to_proj_dict)
            self.manifest_file_name_to_obj_dict[base_name] = rmf

            # backup file
            copyfile(file_path, file_path + FILE_BACKUP_SUFFIX)

            # write to file
            rmf.tree.write(file_path)

    def  validate_remote_repositories_state_helper(self, url, new_rev):
        #check that new rev does not exist on remote

        if new_rev.startswith(REF_BRANCH_PREFIX):
            return SGlobalFuncs.is_branch_exist_in_remote_repo(url, new_rev, False)
        
        if new_rev.startswith(REF_TAG_PREFIX):
            return SGlobalFuncs.is_tag_exist_in_remote_repo(url, new_rev, False)        
        
        return True # fail            
            
    # rename/ refactor
    def validate_remote_repositories_state(self):   
        #check that all branches/tags to be created, are not on remote
        
        '''
        list of  tuples. Each tuple is of length of 4:
        index 0 : URL to check
        index 1 : revision to check
        index 2 : boolean which marks expected result - True if we expect the branch to exist on remote, False if we do not
                  expect the branch to exist on remote
        ''' 
        check_remote_list = []
        
        # add all entries from INPUT_FILE_ADDITIONAL_SD_KEY_NAME SD:
        for (k,v) in self.new_revisions_dict[INPUT_FILE_ADDITIONAL_SD_KEY_NAME].items():
            url = SGlobalFuncs.build_url_from_full_repo_name(ARM_MRR_REMOTE, k)
            check_remote_list.append( ( url, v[1]) )
            
        for file_obj in self.manifest_file_name_to_obj_dict.values():
            # file_obj is CRepoManifestFile
            for (k,v) in file_obj.repo_name_to_proj_dict.items():
                # k is a repository name and v is a matching project 
                url = SGlobalFuncs.build_url_from_full_repo_name(file_obj.remote_key_to_remote_dict[v.remote_key], v.full_name)
                new_ref = self.get_new_ref_from_new_revision_dict(file_obj.base_name, k)
                if not new_ref:
                    continue
                if v.isArmMRR:
                    # for Arm MRRs check both current revision and new revision
                    # (since we need to clone and change branch from)
                    check_remote_list.append( ( url, new_ref) )
                    
        self.logger.debug("===check_remote_list:")
        self.logger.debug(pformat(check_remote_list))
        
        # check concurrently that none of the repositories in mrr_url_set 
        # has a branch called 'create_branch_name'
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(check_remote_list)) as executor:
            future_to_git_url = {
                    executor.submit(self.validate_remote_repositories_state_helper, tup[0], tup[1]): 
                    tup for tup in check_remote_list
                }
            for future in concurrent.futures.as_completed(future_to_git_url, MAX_TMO_SEC):
                tup = future_to_git_url[future]                
                result = future.result()
                if result == True:
                    raise argparse.ArgumentTypeError(
                            "revision {} exist on remote url {}".format(tup[1], tup[0]))
                        
        
    def dict_raise_on_duplicates(self, ordered_pairs):
        """Reject duplicate keys."""
        d = {}
        for k, v in ordered_pairs:
            if k in d:
                raise ValueError("duplicate key: %r" % (k,))
            else:
                d[k] = v
        return d    
    
    def revalidate_input_file(self):
        
        # Check that :
        # 1. All file-specific SDs point to actual files
        # 2. All repository names in SDs points to at lease one actual project  in manifest files
        for file_name, sd in self.new_revisions_dict.items():
            if file_name == INPUT_FILE_ADDITIONAL_SD_KEY_NAME:
                continue

            # checking 1
            if file_name != INPUT_FILE_COMMON_SD_KEY_NAME:
                found = file_name in self.manifest_file_name_to_obj_dict
                if found:
                    break

                if not found:
                    mbl_manifest_path = self.repo_name_to_git_repo_dict[MBL_MANIFEST_REPO_NAME].clone_dest_path
                    raise ValueError("main entry key {} in user input file is not found in {}".format(
                            file_name, os.path.join(mbl_manifest_path, file_name + ".xml")))

            # checking 2
            for repo_name in sd:
                found = False
                for f in self.manifest_file_name_to_obj_dict.values():
                    if repo_name in f.repo_name_to_proj_dict:
                        found = True
                        break
                if not found:
                    raise ValueError("invalid input file : entry {}/{} not found in manifest files!",
                                     file_name, repo_name)

        self.validate_remote_repositories_state()  
        
    def parse_and_validate_input_file(self):        
        # Open the given input and parse into new_revision_dict dictionary, detect duplicate main key
        with open(self.args.refs_input_file_path, encoding='utf-8') as data_file:            
            self.new_revisions_dict = json.loads(data_file.read(), object_pairs_hook=self.dict_raise_on_duplicates)
                      
        # check that exist at least INPUT_FILE_ADDITIONAL_SD_KEY_NAME key with a sub-dictionary that comply with :
        # 1. All pairs are (key, lists of length 2), and the value list must have distinct values
        # 2. armmbed/mbl-manifest repository exist in sub-dictionary
        if not INPUT_FILE_ADDITIONAL_SD_KEY_NAME in self.new_revisions_dict:
            raise ValueError("main entry key %s could not be found in user input file" % INPUT_FILE_ADDITIONAL_SD_KEY_NAME)   
        if not MBL_MANIFEST_REPO_NAME in self.new_revisions_dict[INPUT_FILE_ADDITIONAL_SD_KEY_NAME]:
            raise ValueError("%s key is not found could not be found in user input file under %s" 
                             % (MBL_MANIFEST_REPO_NAME,INPUT_FILE_ADDITIONAL_SD_KEY_NAME))
        for l in self.new_revisions_dict[INPUT_FILE_ADDITIONAL_SD_KEY_NAME].values():
            if len(l) != 2:
                raise ValueError("Bad length for list %s - All lists under key %s in user input file must be of length 2!" 
                                     % (l,INPUT_FILE_ADDITIONAL_SD_KEY_NAME)) 
            if l[0] == l[1]:
                raise ValueError("Bad list %s - non-distinct values under key %s in user input file!" 
                                     % (l,INPUT_FILE_ADDITIONAL_SD_KEY_NAME))             
        #set the clone ref for mbl-manifest 
        self.mbl_manifest_clone_ref = self.new_revisions_dict[INPUT_FILE_ADDITIONAL_SD_KEY_NAME][MBL_MANIFEST_REPO_NAME][0]
                                               
        # Do not allow any repo name under common SD to apear in any other SD pair as key
        # Do not allow any repo name under additional SD to apear in any other SD pair as key        
        # l carry a merged list of all pairs which are not in common/additional SDs
        l = []
        for (key, val) in self.new_revisions_dict.items():
            if (key != INPUT_FILE_COMMON_SD_KEY_NAME) and (key != INPUT_FILE_ADDITIONAL_SD_KEY_NAME):
                l += val        
        if l:
            if INPUT_FILE_COMMON_SD_KEY_NAME in self.new_revisions_dict:
                for key in self.new_revisions_dict[INPUT_FILE_COMMON_SD_KEY_NAME].keys():
                    if key in l:
                        raise ValueError("Invalid input in file {} : "
                                         "key {} found in {} but also in other file specific file SDs!".format(
                                         self.args.refs_input_file_path, key, INPUT_FILE_COMMON_SD_KEY_NAME))
            if INPUT_FILE_ADDITIONAL_SD_KEY_NAME in self.new_revisions_dict:
                for key in self.new_revisions_dict[INPUT_FILE_ADDITIONAL_SD_KEY_NAME].keys():
                    if key in l:
                        raise ValueError("Invalid input in file {} : "
                                         "key {} found in {} but also in other file specific file SDs!".format(
                                         self.args.refs_input_file_path, key, INPUT_FILE_ADDITIONAL_SD_KEY_NAME))            
         
          
    def get_new_ref_from_new_revision_dict(self, sd_key_name, repo_name):
        if (sd_key_name in self.new_revisions_dict) and (repo_name in self.new_revisions_dict[sd_key_name]):
            if sd_key_name == INPUT_FILE_ADDITIONAL_SD_KEY_NAME:
                return self.new_revisions_dict[sd_key_name][repo_name][1]
            return self.new_revisions_dict[sd_key_name][repo_name]
        if repo_name in self.new_revisions_dict[INPUT_FILE_COMMON_SD_KEY_NAME]:
            return self.new_revisions_dict[INPUT_FILE_COMMON_SD_KEY_NAME][repo_name]
        return None
            
    def create_and_update_new_revisions_worker(self, remote, name_prefix, short_name, clone_base_path, cur_rev, new_rev):
        try:
            repo = CGitRepository(remote, name_prefix, short_name, clone_base_path, cur_rev)

            new_rev_short = new_rev.rsplit("/", 1)[1]

            # Create the new branch/tag
            if new_rev.startswith(REF_BRANCH_PREFIX):
                new_branch = repo.handle.create_head(new_rev_short)
                assert new_branch.commit == repo.handle.active_branch.commit
                new_branch.checkout()
                new_rev = new_branch
            else:
                cur_rev_short = cur_rev.rsplit("/", 1)[1]
                new_tag = repo.handle.create_tag(new_rev_short, ref=repo.handle.active_branch.commit)
                assert new_tag.commit == repo.handle.active_branch.commit
                assert new_tag.tag is None
                new_rev = new_tag

            if not repo.full_name in [MBL_MANIFEST_REPO_NAME, MBL_LINKED_REPOSITORIES_REPO_NAME]:
                self.repo_push(repo, new_rev)

            return repo
        except:
            logger = logging.getLogger(module_name)
            logger.error("Unexpected error! {}".format(sys.exc_info()[0]))
            raise

    def update_mbl_linked_repositories_conf_helper(self, git_repo):

        # check if file exist
        file_path = os.path.join(git_repo.clone_dest_path, MBL_LINKED_REPOSITORIES_REPO_PATH)
        if not os.path.exists(file_path):
            raise FileNotFoundError("File %s not found!" % file_path)

        is_commit = False

        # Open the file, traverse all over the INPUT_FILE_ADDITIONAL_SD_KEY_NAME SD repositories, and replace
        # We expect file structure, where each element represents a linked repository has 3 settings : 1) options 2) repo URL 3) SRCREV in that order
        # We are going to locate the repo name and change the SRCREV
        for repo_name in self.new_revisions_dict[INPUT_FILE_ADDITIONAL_SD_KEY_NAME].keys():
            if not repo_name in [MBL_MANIFEST_REPO_NAME, MBL_LINKED_REPOSITORIES_REPO_NAME]:
                # Create backup
                copyfile(file_path, file_path + FILE_BACKUP_SUFFIX)

                with in_place.InPlace(file_path) as file:
                    next_line_replace = False
                    for line in file:
                        if line.lower().find("git@github.com/" + repo_name) != -1:
                            active_branch = self.additional_repo_name_to_git_repository_dict[repo_name].handle.active_branch
                            hash = active_branch.commit
                            branch_name = active_branch.name

                            if line.find(";branch=") != -1:
                                matches = re.findall(r';branch=(.+?);', line)  # match text between two quotes
                                for m in matches:
                                    line = line.replace(';%s;' % m, ';branch=%s;' % (branch_name))

                            # TODO : replace former line or reformat file..
                            next_line_replace = True
                        elif next_line_replace:
                            if (line.find("\"") == line.rfind("\"") or line.count("\"") != 2):
                                raise SyntaxError("Bad format for file [{}] in line [{}]".format(file_path, line))

                            matches = re.findall(r'\"(.+?)\"', line)  # match text between two quotes
                            for m in matches:
                                line = line.replace('\"%s\"' % m, '\"%s\"' % (hash))
                            next_line_replace = False
                        file.write(line)
                        is_commit = True

        if is_commit:
            l = git_repo.handle.index.add([file_path], write=True)
            assert len(l) == 1
            git_repo.handle.index.commit("release manager automatic commit")

        self.repo_push(git_repo, git_repo.handle.active_branch)


    def update_mbl_linked_repositories_conf(self):

        # update all MBL_LINKED_REPOSITORIES_REPO_NAME repositories
        if MBL_LINKED_REPOSITORIES_REPO_NAME in  self.additional_repo_name_to_git_repository_dict:
            self.update_mbl_linked_repositories_conf_helper(self.additional_repo_name_to_git_repository_dict[MBL_LINKED_REPOSITORIES_REPO_NAME])
        for fo in self.manifest_file_name_to_obj_dict.values():
            if MBL_LINKED_REPOSITORIES_REPO_NAME in fo.repo_name_to_proj_dict:
                self.update_mbl_linked_repositories_conf_helper(fo.repo_name_to_proj_dict[MBL_LINKED_REPOSITORIES_REPO_NAME].git_repository)


    def clone_and_create_new_revisions(self):
        
        # Clone all additional and Arm MRR repositories, concurrently, checkout current revision
        clone_tup_list = []
        # clone all additional repositories under self.tmpdirname.name
        for (main_key, sd) in self.new_revisions_dict.items():
            for (key, rev) in sd.items():
                if main_key == INPUT_FILE_ADDITIONAL_SD_KEY_NAME:                      
                    if key != MBL_MANIFEST_REPO_NAME:                        
                        prefix, name = key.rsplit("/", 1)
                        clone_tup_list.append( (key, ARM_MRR_REMOTE, prefix, name, self.tmpdirname.name, rev[0], rev[1], main_key) )
        
        # Clone all Arm MRRs, each one on a sub-folder belong to the file. 
        # For example, for default.xml, all matching repos will be cloned under <self.tmpdirname.name>/default/
        for file_obj in self.manifest_file_name_to_obj_dict.values():
            for (name, proj) in (file_obj.repo_name_to_proj_dict.items()):
                new_ref = self.get_new_ref_from_new_revision_dict(file_obj.base_name, proj.full_name)
                if proj.isArmMRR and new_ref:
                    prefix, name = proj.full_name.rsplit("/", 1)

                    clone_tup_list.append((proj.full_name, file_obj.remote_key_to_remote_dict[proj.remote_key],
                            prefix, name, os.path.join(self.tmpdirname.name, file_obj.base_name), proj.revision, new_ref, file_obj.base_name))

        self.logger.debug("=== clone_tup_list:")
        self.logger.debug(pformat(clone_tup_list))
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(clone_tup_list)) as executor:
            future_to_git_url = {
                    executor.submit(self.create_and_update_new_revisions_worker, tup[1], tup[2], tup[3], tup[4], tup[5], tup[6]):
                    tup for tup in clone_tup_list
                }

            for future in concurrent.futures.as_completed(future_to_git_url, MAX_TMO_SEC):
                tup = future_to_git_url[future]                
                result = future.result()                
                if result == None:
                    raise argparse.ArgumentTypeError(
                            "revision {} exist on remote url {}".format(tup[1], tup[0]))
                else:
                    if tup[7] == INPUT_FILE_ADDITIONAL_SD_KEY_NAME:
                        self.additional_repo_name_to_git_repository_dict[tup[0]] = result
                    else:
                        self.manifest_file_name_to_obj_dict[tup[7]].repo_name_to_proj_dict[tup[0]].git_repository = result

    # Costume action - check that the given file path exist on local host
    ###############################################################    
    class StoreValidFile(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            file_path = os.path.abspath(values)
            if not os.path.isfile(file_path):
                raise argparse.ArgumentTypeError(
                  "The path %s does not exist!" % file_path
                )
            filename, file_extension = os.path.splitext(ntpath.basename(file_path))
            if not file_extension == ".json":
                raise argparse.ArgumentTypeError(
                    "File %s does not end with '.json' prefix!" % file_path
                )
            setattr(namespace, self.dest, file_path)

    def finalize(self):
        repo = self.additional_repo_name_to_git_repository_dict[MBL_MANIFEST_REPO_NAME]
        repo.handle.git.add(update=True)
        repo.handle.index.commit("release manager automatic commit")
        self.repo_push(repo, repo.handle.active_branch)

    # Define and parse script input arguments
    ###############################################################
    def get_argument_parser(self):
        parser = argparse.ArgumentParser(
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            description=module_name + " script",
        )
                    
        parser.add_argument(
            "refs_input_file_path",
            action=self.StoreValidFile,
            help="Path to update.json file which holds a dictionary of pairs (repository name, ref / hash). For more"
            " information and exact format see mbl-tools/build-mbl/README.md."
        )
        
        parser.add_argument(
            "-v",
            "--verbose",
            help="increase output verbosity",
            action="store_true"
        )

        parser.add_argument(
            "-c",
            "--controlled_mode",
            help="Prompt before each significant step",
            action="store_true"
        )

        parser.add_argument(
            "-s",
            "--simulate",
            help="Do not push to remote, everything else will be executed exactly the same but nothing is actually pushed into remote.",
            action="store_true"
        )
        
        return parser


def _main():

    # Create and initialize a release manager object
    rm = CReleaseManager()    

    # Parse JSON references input file
    rm.parse_and_validate_input_file()
    
    # Clone the manifest repository and parse its xml files into database
    rm.process_manifest_files()
      
    # Some more things to validate in input file after parsing both files
    rm.revalidate_input_file()  
    
    # Update new_revision for all manifest files projects and create reference (where needed on remot Git repositories)
    rm.clone_and_create_new_revisions()

    # update all files MBL_LINKED_REPOSITORIES_REPO_PATH in repositories MBL_LINKED_REPOSITORIES_REPO_NAME
    rm.update_mbl_linked_repositories_conf()

    # Commit MBL_LINKED_REPOSITORIES_REPO_NAME and MBL_MANIFEST_REPO_NAME and push to remote
    rm.finalize()

# TODO-change this later on
if __name__ == "__main__":
    sys.exit(_main())