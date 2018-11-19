## JSON Config File Overview - (TODO-traverse one last time and fix)
# TODO - need to update that all pairs in _additional_ must be (key, list) type

Add revision definition :
Attribute `revision`: Name of the Git branch the manifest wants
to track for this project.  Names can be relative to refs/heads
(e.g. just "master") or absolute (e.g. "refs/heads/master").
Tags and/or explicit SHA-1s should work in theory, but have not
been extensively tested.  If not supplied the revision given by
the remote element is used if applicable, else the default
element is used.

add section for lined repos. we expect exact file stcurture with no multi lines.


The Mbed Linux OS  Release Manager, used by mbl-tools, receives as an input a JSON format configuration file. The file holds a main dictionary of (***main key***, value) pairs. A main key must belong to one of 3 types:
1. A manifest file name matching a Git repo manifest file that must exist in armmbed/mbl-manifest repository (without the '.XML' suffix). For example : the key 'default' will match the default.xml file, and the sub-dictionary value matched by 'default' will hold pairs of (repository name, new revision).
2. A special key called ***\_common\_*** . We assume that no manifest file is called '\_common\_.xml'. This key holds to a dictionary which holds default (repository name, new revision) pairs.
3. A special key called ***\_additional\_***.We assume that no manifest file is called '\_additional\_.xml'.  This key holds to a dictionary which holds additional (repository name, new revision) pairs.  For example mbl-tools, mbl-manifest, mbl-core. This key MUST be in the dictionary, as it provides the armmbed/mbl-manifest pair with the revision to clone the repository from.

All keys point to a sub-dictionary (we call it **SD**) values. A non-special SD (as described in section 1) is called ***file-specific SD***. All keys must be unique inside main dictionary or a sub-dictionary (or file parsing will fail).

## SD Pair rules
* We define an **SD pair** - an element in an SD which consist of:
  1. **SD pair key** - full repository name (e.g 'armmbed/meta-mbl' or 'git/meta-freescale').
  2. **SD pair value** - a new **revision** or a ***current/new revision*** list.This can be:  
      * Git branch or tag name (both are called ***git ref***).A Git branch ref must start with a **refs/heads/** prefix. A Git tag ref must start with a **refs/tags/** prefix.
      * A full commit hash  (e.g SHA-1).

* Keys in '_additional_' SD must not overlap with any keys in any other SD.
* Keys in '_common_' SD must not overlap with any keys in any other SD.
* Keys in a file-specific SD may overlap with keys in other file-specific SD.

## Type of SD Pairs and remote Git ref creation

1. **MRRs (Manifest Referenced Repository)** - These are given in file-specific SDs or in '_common_' SD. These are all the repository project elements which can be found in mbl-manifest repository
xml manifest files.We can further subdivide this type to 2 subtypes:

    A. **Arm MRRs (Arm owned Manifest Referenced Repositories)** -
    * ref (tag or branch) MUST NOT exist on the remote repository. Script will create such ref on the remote.
    * commit hash MUST exist on the remote, new ref is not created.

    B. **Non-Arm MRRs - (Community or Linaro owned Manifest Referenced Repositories)** - ref or commit hash must exist
        on the remote repository.

2. **Additional Arm managed repositories** - These are given '_additional_' SD.These are repository names which are not pointed in any of the mbl-manifest repository xml files.
Only branch or tag names can be given for these repositories (with the same rules as in 1.A.).
'armmbed/mbl-manifest' is such a type, which MUST be given in the JSON file.
If 'armmbed/meta-mbl' is given, the file meta-mbl/conf/dist/mbl-linked-repositories.conf will be modified accordingly to point
into the new linked refs (if such exist).

**Comments** :
It is possible to give only some of the MRR/Additional Arm managed repositories. In this case, only part of the project elements in the manifest files will be modified (and only for part of them a remote ref will be created).

## Format example:
```
{
	"_aditional_": {
		"armmbed/mbl-manifest": ["refs/heads/manifest_dev_current1", "refs/heads/manifest_dev_internal_1"],
		"armmbed/meta-mbl": ["refs/heads/manifest_dev_current2", "refs/heads/manifest_dev_internal_1"]
	},
	"_common_": {
		"git/meta-freescale": "748e958db5e8c9cede4186c594a7b5ade314a25a",
		"git/meta-raspberrypi": "refs/tags/tag_1",
		"git/additional_non_mrr_repo": "refs/heads/branch_name_2"
	},

	"reference-apps-internal": {
		"armmbed/meta-mbl-reference-apps": "refs/heads/branch_name_3",
		"armmbed/meta-3": "refs/heads/branch_name_11"
	},
	"reference-apps": {
		"armmbed/meta-mbl-reference-apps": "refs/heads/branch_name_4",
		"armmbed/meta-4": "refs/heads/branch_name_11"
	}
}

```
In this example There are 3 pairs with the keys - COMMON, reference-apps-internal and reference-apps.

**'COMMON' dictionary**:
1. The 1st element is an Arm MRR (name prefix with armmbed, and remote is github). It can be found in default.xml manifest file. The new value is a branch ref.
   Before modification to default.xml:
   <project name="armmbed/meta-mbl" path="layers/meta-mbl" remote="github"/>
   After modification:
   <project name="armmbed/meta-mbl" path="layers/meta-mbl" revision="refs/heads/branch_name_1" remote="github"/>
   In this example, script checks that such branch does not exist on remote, creates a  branch from master branch (the default) and push to remote.
2. The 2nd element is a non-Arm MRR. project entry will be modified accordingly, while a commit hash is acceptable for this pair type.
    No branch will be created, script only checks that such hash exist on remote.
3. The 3rd element is very similar to the 2nd. This time a tag is given ('refs/tags/').
4. The 4th element has the mbl-manifest as a key, which must be in any JSON file. The ref is a branch to create and update the remote.
5. The 5th element is an additional Arm managed repository. A new branch branch_name_2 will be created and pushed to remote. Also, since meta-mbl is given, mbl-linked-repositories.conf will be scanned for the repository name git/additional_non_mrr_repo and updated accordingly with the new branch name branch_name_2 to be linked to from all pointing repositories.

**'reference-apps-internal' and reference-apps dictionaries**:
1. The key armmbed/meta-mbl-reference-apps repeats in both dictionaries, but does not appear in COMMON sub-dictionary. This is legal.
2. Both dictionaries hold also 2 distinct key pairs.
3. If at least one of the dictionaries would hold (for example) the pair :
"armmbed/meta-mbl" : "refs/heads/branch_name_1", the script would exist with an error since the key "armmbed/meta-mbl" apears in 'COMMON'.
