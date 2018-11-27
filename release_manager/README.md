## Release manager update JSON format

The Mbed Linux OS  ***Release Manager***, used by mbl-tools (or can also be used directly from the command line), receives an input JSON input file. By convention, one should use the name ***update.json*** as the file name (or ***update_%.json*** if there are multiple files in the same folder).  
The file holds a dictionary of (***main key***, value) pairs. Each main key points to a sub-dictionary (**SD**) as its value. An SD pointed by an actual file name key (as described in section 1) is called ***file-specific SD***.  
A  pair must belong to one of 3 types:
1. ***File specific SD*** - A manifest file name (without the '.xml' suffix) matching a Git repo manifest file that must exist in armmbed/mbl-manifest repository root. Using that type, a specific  XML manifest file will be updated ( and some Arm MRRs remotes might be updated as well). For example: the key 'default'  match the default.xml file, and the sub-dictionary (***SD***) value matched by 'default' holds pairs of (repository name, new revision to be created).
2. A special key  ***\_common\_*** -  SD value for that key described a common update on all XML files in mbl-manifest repository root. We assume that no manifest file is called '\_common\_.xml'. This key points to a dictionary (repository name, new revision) which holds a common update mechanism. Whenever our update is needed accross all manifest files, with a single release branch name, the use of _common_ is the simplest.  
For example, let's assume that  we have a repository called mbl-example in 3 files: default.xml, internal.xml and costume.xml. We want to have the same new revision branch new_rev1 in all 3 manifest files. We can add a pair with a key armmbed/mbl-example and a value as a branch new_rev1 under '_common_' which will refer in a common way to all 3 files. That means: check out from the revision pointed in the manifest file, create a new branch new_rev1 and push to remote. Also, modify the new branch name in all 3 files. All those operations can be described in a single entry when found in _common_.
3. A special key  ***\_additional\_*** - SD value for that key describes Arm additional repository needed changes. We assume that no manifest file is called '\_additional\_.xml'. This key points to a dictionary which holds pairs of (repository name, [checkout_revision, new revision]) pairs. The value us a list of length 2, with the 1st element for the checkout revision and the second value for the new revision to be created.The repositories under this main keys are Arm managed repositories which cannot be found in any manifest file. For example: mbl-tools, mbl-manifest, mbl-core and mbl-cli. This key MUST be in every file, as it provides the armmbed/mbl-manifest pair with the revision to clone the repository from.

All main keys must be unique inside the main dictionary or inside a sub-dictionary - else file parsing will fail.
**Additional Comments**:
* It is possible to give only some of the MRR/Additional Arm managed repositories. In this case, only part of the project elements in the manifest files will be modified (and only for part of them a remote revision will be created).
* At the time of writing this document, mbl-linked-repositories.conf file doesn't have any strict formatting. This might  cause issues when the file is being modified as part of a manual development process. We might impose strict formatting on that file.
* Currently, there is no operation like 'branch detach from revision' or 'pin to revision'. This can be achieved with extra effort. Might be added later.

## SD Pair rules
* We define an **SD pair** - an element in SD which consist of:
  1. **SD pair key** - full repository name (e.g 'armmbed/meta-mbl' or 'git/meta-freescale').
  2. **SD pair value** - a new **revision** or a ***current/new revision*** list.This can be:  
      * Git branch or tag name (both are called ***Git ref***).A Git branch ref must start with a **refs/heads/** prefix. A Git tag ref must start with a **refs/tags/** prefix.
      * A full (40 hexadecimal characters) ***Git commit hash***  (e.g SHA-1).

  We define a ***revision*** as a Git commit hash or a Git ref.

* Keys in '_additional_' SD must not overlap with any keys in any other SD.
* Keys in '_common_' SD must not overlap with any keys in any other SD.
* Keys in a file-specific SD may overlap with keys in other file-specific SD.
* Values in '_additional_' SD are always a list of size 2:
  1. The first value is the where to checkout from and must be a revision.
  2. The second value is a new Git ref to be created.

## Type of SD Pairs and remote Git ref creation

1. **MRRs (Manifest Referenced Repository)** - These are given in file-specific SDs or in '_common_' SD. These are all the repository project elements which can be found in mbl-manifest repository root, inside the xml manifest files. We can further subdivide this type to 2 subtypes:

    A. **Arm MRRs (Arm owned Manifest Referenced Repositories)** -
    Will usually have the prefix name 'armmbed' on the repository project name, and an origin URL prefix 'ssh://git@github.com'.
    * Git ref (tag or branch) MUST NOT exist on the remote repository. The script will create such ref on the remote.
    * Git commit hash MUST exist on the remote, new ref is not created.

    B. **Non-Arm MRRs - (Community or 3rd party Manifest Referenced Repositories)** - ref or commit hash must exist on the remote repository.

2. **Additional Arm managed repositories** - These are given in '_additional_' SD. These are repository names which are not pointed in any of the mbl-manifest repository xml files. ***'armmbed/mbl-manifest'*** is such a type, which MUST be given in the JSON file. If 'armmbed/meta-mbl' is given, the file ***meta-mbl/conf/dist/mbl-linked-repositories.conf*** will be modified accordingly to point into the new linked references (if such exist).

## Validity checks examples:

In this section we will go through a valid and invalid JSON files examples. Initially, the script checks that the JSON file is legal and formatted according to RFC 4627 (The application/json Media Type for JavaScript Object Notation (JSON), July 2006). If JSON format check fails, an exception will be raised.  
After checking format , there are many other validity checks done, in order to make sure that the actual input is valid.  
To keep things simple, each example is kept short. We do not demonstrate 'real world' examples, in order to be able to focus on the principles.

### Example 1 - a valid update file
```
{
	"_additional_": {
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
* _additional_ - holds an SD with 2 pairs, each key points to a list of length 2. In one of them the script branches from a branch, in another on it branches from a tag.
* reference-apps / reference-apps-internal - both hold 2 pairs each one. The repository armmbed/meta-mbl-reference-apps can be found in both files, but the new branch created is different. This is perfectly legal.
* _common_ - holds 3 repositories to be changed across all XML files.The "git/meta-freescale_2" is a none Arm MRR repository. The prefix armmbed will always point to an Arm MRR or ARM additional repository, which is not the case here (prefix git). armmbed/meta-mbl is the only repository with armmbed/mbl-manifest which will have a new commit (modified files). That will happen in case the the mbl-linked-repositories.conf file will needed to be updated for some of it's entries (in real world - mbl-core for now is the only one needed to be updated).

### Example 2 - invalid JSON file - no _additional_ main key
```
	"_common_": {
    "armmbed/meta-1": "refs/heads/new2",
		"git/meta-freescale_2" : "refs/tags/new24"
	}
}
```
What is invalid?
The file doesn't have an _additional_ main key. Script can't checkout mbl-manifest.

### Example 2 - invalid JSON file - mbl-manifest is missing
```
"_additional_": {
  "armmbed/mbl-tools": ["refs/tag/origin2", "refs/heads/new2"]
},

"_common_": {
    "armmbed/meta-1": "refs/heads/new2",
		"git/meta-freescale_2" : "refs/tags/new24"
	}
}
```
What is invalid?
The file does have an _additional_ main key, but the SD does not have armmbed/mbl-manifest.

### Example 3 - invalid JSON file - duplicated repository
```
"_additional_": {
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
armmbed/meta-1 repeats in _additional_ and in _common_.

### Example 4 - invalid JSON file - duplicated repository
```
"_additional_": {
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
armmbed/meta-1 repeats in _additional_ and in reference-apps.


### Example 5 - invalid JSON file - duplicated repository
```
{
	"_additional_": {
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

### External Links

* https://wiki.yoctoproject.org/wiki/Stable_branch_maintenance
