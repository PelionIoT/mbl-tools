# Release manager Overview
### Definitions
* **MRR** - Manifest Referenced Repository - a repository referenced in a Repo manifest file (in the mbl-manifest repo).
* **Arm MRR** - Arm owned Manifest Referenced Repository.
* **Non-Arm MRR**	- Community (or Linaro / 3rd party) owned Manifest Referenced Repository.
* **External Mbed Linux OS Managed repository** - any repository which is managed by The MBed Linux OS project, but is not an Arm MRR. In short, we call it here an **external repo**.
* **Git branch** - a reference (represented as a name) to a commit in a chain of commits. A default branch is called master and points to the branch HEAD (which is the last commit).
* **Git tag** - A tag represents a version of a particular branch at a moment in time.
* **Git ref** - a git tag, local or remote branch is called a ref (short for a reference). Anything that points to a commit is called a Git ref, or just ref.
* **Commit hash** - A Git commit can be represented by multiple ways. One of the ways to represent a commit is by its Full Commit ID - 40 hexadecimal characters that specify a 160-bit SHA-1 hash.
* **revision** - A git Ref or a Commit hash.

## 1. Purpose of the Script
This script is used in order to create a release branch based on a user-provided JSON configuration file. It modifies Google Repo manifest files in armmbed/mbl-manifest, and mbl-linked-repositories.conf in armmbed/meta-mbl. It then commits these two repositories, creates a new branch/tag according to the provided JSON file and pushes all modifications to GitHub.
In more details, it performs the next significant operations:  
1. Clone the mbl-manifest repository and checks out a new revision.
1. Modify specified XML manifest files present in the new branch of mbl-manifest by setting the revision for each projects
1. Commit the changes made to the created mbl-manifest branch/tag and push the branch to a remote repository.
1. Does the following for each projects with modified revisions in mbl-manifest Google Repo manifest files:
  * If the repository is an Arm-MRR, clone from the revision stated in the manifest file, create a new branch/tag, and push the branch to the remote repository.
  * If the repository is not an Arm-MRR, simply set the revision of the projects. The revision in the user configuration file must be an existing revision in the remote repository.
1. External Arm-managed repositories can also be provided in the user configuration file. After cloning the repository from a specified revision, a new branch/tag is created and pushed to the remote repository.
1. One of the configuration files in the newly created `meta-mbl` tag/branch (`mbl-linked-repositories.conf`) is optionally updated to point to a specified commit sha in the `mbl-core` repository.

## 2. How the script works
#### General steps:
1. Validate user input.
1. Clone the manifest repository mbl-manifest according to user input and parse it's Google Repo manifest files into a database.
1. Validate dependencies between user input and manifest files. Check for inconsistencies.
1. Clone all repositories that needs to have commits and/or new branches (according to user input). This is done using multiple threads and waiting for a timeout. At the same time update Google Repo manifest files with the new revisions. Repositories are cloned per Google Repo manifest file name key, in a sub-folder.For example, for default.xml script clones into a folder called 'default'. Some Google Repo manifest files might have identical repositories with different input revision, that's why we do that. External repositories are cloned into the destination temporary folder root.
1. Check if meta-mbl/conf/dist/mbl-linked-repositories.conf need to be updated. Updated if needed, commit and push. Push is done even if conf file was not updated. In that case script will treat this repository such as every repository that needs to be changed (The only repository guaranteed to have a commit is mbl-manifest).
1. Push all repositories. This is done using multiple threads and waiting for a timeout.
1. Print a summary of significant operations.

#### Other capabilities:
* The `-r` option can be used when running the application to delete the working directory created under `/tmp`.
* The `-s` option can be used to perform all operations except pushing to remote repositories.
* The `-d` option can be used to request interactive confirmation before pushing anything to a remote repository. User may check the status of the local repository, validate changes and then confirm the push or exit the script.

## 3. How to use the script
Assumptions:
* The script should always run on a Linux host machine.
* Python3 is installed (script was tested on Python 3.5.2).
* The user has write access to Mbed Linux OS product and supporting product repositories on GitHub. For more details on what are they, see: https://confluence.arm.com/display/mbedlinux/Repositories.
* We use venv. Else, user needs to install in_place and gitpython packages.

Here we will demonstrate how to run script using virtualenv (venv).
prerequisites:
* Install pip3 if you don't have it installed:
```
$ sudo apt-get install python3-pip
$ pip3 --version
pip 18.1 from ... (python 3.5)

```
* Create my_venv under /tmp/my_venv , and start it:
```
$ cd /tmp
$ python3 -m venv my_venv
$ source my_venv/bin/activate
(my_venv) $
```
* Now we are inside a Python3 virtual environment 'my_venv'. Lets clone the mbl-tools repository and install the script package:
```
(my_venv) $ git clone git@github.com:ARMmbed/mbl-tools.git
(my_venv) $ cd mbl-tools/mbl-release-manager/
(my_venv) $ python setup.py install
```
* After installing the script's package, mbl-release-manager can be run from anywhere. It resides under /tmp/my_venv/mbl-release-manager/venev/bin.
* Type mbl-release-manager -h for help. A typical run will start by simulating and look like that (after creating an update.json file locally):
```
(my_venv) $ mbl-release-manager -s -r update.json
```
* To exit venv after script is done type:
```
(my_venv) $ deactivate
$
```

## 4. User Input
The Mbed Linux OS  **Release Manager**, can be installed to be ran as a command or can be ran as a script. It receives a JSON formatted configuration file as input. The file name must end with `.json`. A commonly recommended used naming scheme (but not imposed in code) for the configuration file is <release_name>-release-conf.json. i.e For mbl-os-0.5 the configuration file will be named `mbl-os-0.5-release-conf.json`.

The file holds a dictionary of (**main key**, value) pairs. Each main key points to a sub-dictionary (**SD**) as its value. An SD pointed by an actual file name key (as described in section 1) is called **file-specific SD**.  
A  pair must belong to one of 3 types:  
1. **File specific SD** - A manifest file name (without the '.xml' suffix) matching a Git repo manifest file that must exist in any cloned armmbed/mbl-manifest repository root. Using that type, a specific  Google Repo manifest file will be updated ( and some Arm MRRs remotes might be updated as well). For example: the key 'default'  match the default.xml file, and the sub-dictionary (**SD**) value matched by 'default' holds pairs of (repository name, new revision to be created).
1. A special key  **\_common\_** -  SD value for that key described a common update on all Google Repo manifest files in mbl-manifest repository root. We assume that no manifest file is called '\_common\_.xml'. This key points to a dictionary (repository name, new revision) which holds a common update mechanism. Whenever our update is needed across all manifest files, with a single release branch name, the use of _common_ is the simplest.  
For example, let's assume that  we have a repository called mbl-example in 3 files: default.xml, internal.xml and custom.xml. We want to have the same new revision branch new_rev1 in all 3 manifest files. We can add a pair with a key armmbed/mbl-example and a value as a branch new_rev1 under '_common_' which will refer in a common way to all 3 files. That means: check out from the revision pointed in the manifest file, create a new branch new_rev1 and push to remote. Also, modify the new branch name in all 3 files. All those operations can be described in a single entry when found in _common_.
1. A special key  **\_external\_** - SD value for that key describes Arm non-manifest managed repository needed changes. We assume that no manifest file is called '\_external\_.xml'. The value for this key is a dictionary which holds pairs of (repository name, [checkout_revision, new revision]) pairs. The value us a list of length 2, with the 1st element for the checkout revision and the second value for the new revision to be created.The repositories under this main keys are Arm managed repositories which cannot be found in any manifest file. For example: mbl-tools, mbl-manifest, mbl-core and mbl-cli. This key MUST be in every file, as it provides the armmbed/mbl-manifest pair with the revision to clone the repository from.

All main keys must be unique inside the main dictionary or inside a sub-dictionary - else file parsing will fail.
**Additional Comments**:
* It is possible to give only some of the MRR/external Arm managed repositories. In this case, only part of the project elements in the manifest files will be modified (and only for part of them a remote revision will be created).
* At the time of writing this document, mbl-linked-repositories.conf file doesn't have any strict formatting. This might  cause issues when the file is being modified as part of a manual development process. We might impose strict formatting on that file.
* Currently, there is no operation like 'branch detach from revision' or 'pin to revision'. This can be achieved with extra effort. Might be added later.

### SD Pair rules
* We define an **SD pair** - an element in SD which consist of:
  1. **SD pair key** - full repository name (e.g 'armmbed/meta-mbl' or 'git/meta-freescale').
  1. **SD pair value** - a new **revision** or a **current/new revision** list.This can be:  
      * Git branch or tag name (both are called **Git ref**).A Git branch ref must start with a **refs/heads/** prefix. A Git tag ref must start with a **refs/tags/** prefix.
      * A full (40 hexadecimal characters) **Git commit hash**  (e.g SHA-1).

  We define a **revision** as a Git commit hash or a Git ref.

* Keys in '_external_' SD must not overlap with any keys in any other SD.
* Keys in '_common_' SD must not overlap with any keys in any other SD.
* Keys in a file-specific SD may overlap with keys in other file-specific SD.
* Values in '_external_' SD are always a list of size 2:
  2. The first value is the where to checkout from and must be a revision. It must exist on the remote.
  2. The second value is a new Git ref to be created. It must not exist on the remote.
* All revisions which refers to non-Arm MRRs repositories, must exist on the remote repository.

### Type of SD Pairs and remote Git ref creation

1. **MRRs (Manifest Referenced Repository)** - These are given in file-specific SDs or in '_common_' SD. These are all the repository project elements which can be found in mbl-manifest repository root, inside the Google Repo manifest files. We can further subdivide this type to 2 subtypes:

    A. **Arm MRRs (Arm owned Manifest Referenced Repositories)** -
    Will usually have the prefix name 'armmbed' on the repository project name, and an origin URL prefix 'ssh://git@github.com'.
    * Git ref (tag or branch) MUST NOT exist on the remote repository. The script will create such ref on the remote.
    * Git commit hash MUST exist on the remote, new ref is not created.

    B. **Non-Arm MRRs - (Community or 3rd party Manifest Referenced Repositories)** - ref or commit hash must exist on the remote repository.

1. **External Arm managed repositories** - These are given in '_external_' SD. These are repository names which are not pointed in any of the mbl-manifest Google Repo manifest files. **'armmbed/mbl-manifest'** is such a type, which MUST be given in the JSON file. If 'armmbed/meta-mbl' is given, the file **meta-mbl/conf/dist/mbl-linked-repositories.conf** will be modified accordingly to point into the new linked references (if such exist).

### Validity checks examples:

In this section we will go through a valid and invalid JSON files examples. Initially, the script checks that the JSON file is legal and formatted according to RFC 4627 (The application/json Media Type for JavaScript Object Notation (JSON), July 2006). If JSON format check fails, an exception will be raised.  
After checking format , there are many other validity checks done, in order to make sure that the actual input is valid.  
To keep things simple, each example is kept short. We do not demonstrate 'real world' examples, in order to be able to focus on the principles.

#### Example 1 - a valid update file
```
{
	"_external_": {
		"armmbed/mbl-manifest": ["refs/heads/origin1", "refs/heads/new1"],		
    "armmbed/mbl-tools": ["refs/tag/origin2", "refs/heads/new2"]
	},

	"_common_": {
    "armmbed/meta-1": "refs/heads/new2",
    "armmbed/meta-mbl": "refs/heads/new28",
    "git/meta-freescale_2" : "refs/tags/new24"
	},

  "reference-apps": {
    "armmbed/meta-mbl-reference-apps": "refs/heads/new4",
    "armmbed/meta-4": "refs/heads/new_11"
  },

	"reference-apps-internal": {
		"armmbed/meta-mbl-reference-apps": "refs/heads/branch_name_3",
		"armmbed/meta-3": "refs/heads/branch_name_11"
	}
}
```
In this example There are 4 main pairs: 2 special pairs and 2 file-specific pairs.
Important things to mention:
* _external_ - holds an SD with 2 pairs, each key points to a list of length 2. In one of them the script branches from a branch, in another on it branches from a tag.
* reference-apps / reference-apps-internal - both hold 2 pairs each one. The repository armmbed/meta-mbl-reference-apps can be found in both files, but the new branch created is different. This is perfectly legal.
* _common_ - holds 3 repositories to be changed across all Google Repo manifest files.The "git/meta-freescale_2" is a none Arm MRR repository. The prefix armmbed will always point to an Arm MRR or ARM external repository, which is not the case here (prefix git). armmbed/meta-mbl is the only repository with armmbed/mbl-manifest which will have a new commit (modified files). That will happen in case the the mbl-linked-repositories.conf file will needed to be updated for some of it's entries (in real world - mbl-core for now is the only one needed to be updated).

#### Example 2 - invalid JSON file - no _external_ main key
```
	"_common_": {
    "armmbed/meta-1": "refs/heads/new2",
		"git/meta-freescale_2" : "refs/tags/new24"
	}
}
```
What is invalid?
The file doesn't have an _external_ main key. Script can't checkout mbl-manifest.

#### Example 2 - invalid JSON file - mbl-manifest is missing
```
"_external_": {
  "armmbed/mbl-tools": ["refs/tag/origin2", "refs/heads/new2"]
},

"_common_": {
    "armmbed/meta-1": "refs/heads/new2",
		"git/meta-freescale_2" : "refs/tags/new24"
	}
}
```
What is invalid?
The file does have an _external_ main key, but the SD does not have armmbed/mbl-manifest.

#### Example 3 - invalid JSON file - duplicated repository
```
"_external_": {
  "armmbed/mbl-tools": ["refs/tag/origin2", "refs/heads/new2"],
  "armmbed/meta-1": "refs/heads/new2"
},

"_common_": {
    "armmbed/meta-1": "refs/heads/new2",
		"git/meta-freescale_2" : "refs/tags/new24"
	}
}
```
What is invalid?
armmbed/meta-1 repeats in _external_ and in _common_.

#### Example 4 - invalid JSON file - duplicated repository
```
"_external_": {
  "armmbed/mbl-tools": ["refs/tag/origin2", "refs/heads/new2"],
  "armmbed/meta-1": "refs/heads/new2"
},

"reference-apps": {
  "armmbed/meta-mbl-reference-apps": "refs/heads/new4",
  "armmbed/meta-4": "refs/heads/new_11",
  "armmbed/meta-1": "refs/heads/new2"
}
```
What is invalid?
armmbed/meta-1 repeats in _external_ and in reference-apps.


#### Example 5 - invalid JSON file - duplicated repository
```
{
	"_external_": {
		"armmbed/mbl-manifest": ["refs/heads/origin1", "refs/heads/new1"],		
    "armmbed/mbl-tools": ["refs/tag/origin2", "refs/heads/new2"]
	},

  "reference-apps": {
    "armmbed/meta-mbl-reference-apps": "1212121212121212121212121212121212121212",
    "armmbed/meta-4": "refs/heads/new_11"
  }
}
```
What is invalid?
armmbed/meta-mbl-reference-apps has a new revision as a Git commit hash. That's impossible. Git commit hash is auto generated. New revisions should always be tag a Git ref - branch or tag.

#### External Links

* https://wiki.yoctoproject.org/wiki/Stable_branch_maintenance
* https://confluence.arm.com/display/mbedlinux/Repositories
