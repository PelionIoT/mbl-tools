## JSON Config File Overview

The Mbed Linux OS  Release Manager, used by mbl-tools, receives as an input a JSON format configuration file.
The file holds a dictionary of pairs (repository name, Git ref):
Key must be unique and hold a full Git repository name (e.g 'armmbed/meta-mbl' or 'git/meta-freescale')
Value is a Git ref which can be a Git branch or tag name, or a full hash character sequence (e.g SHA-1).
For all mbl-manifest xml files, the attribute 'revision' value is modified accordingly, and replaced by the new ref if already exist, or
added to the XML file if does not exist.

## Type of Pairs and remote Git ref creation

1. **MRRs (Manifest Referenced Repository)** - These are all the repository project elements which can be found in mbl-manifest repository
xml manifest files.We can further subdivide this type to 2 subtypes:

    A. **Arm MRRs (Arm owned Manifest Referenced Repositories)** -
    * ref (tag or branch) MUST NOT exist on the remote repository. Script will create such ref on the remote.
    * hash MUST exist on the remote, new ref is not created.

    B. **Non-Arm MRRs - (Community or Linaro owned Manifest Referenced Repositories)** - ref or hash must exist
        on the remote repository.

2. **Additional Arm managed repositories** - These are repository names which are not pointed in any of the mbl-manifest repository xml files.
Only branch or tag names can be given for these repositories (with the same rules as in 1.A.).
'armmbed/mbl-manifest' is such a type, which MUST be given in the JSON file.
If 'armmbed/meta-mbl' is given, the file meta-mbl/conf/dist/mbl-linked-repositories.conf will be modified accordingly to point
into the new linked refs (if such exist).

**Comments** :
It is possible to give only some of the MRR/Additional Arm managed repositories. In this case, only part of the project elements in the manifest files will be modified (and only for part of them a remote ref will be created).

## Format example:
```
{
    "armmbed/meta-mbl" : "refs/heads/branch_name_1",
    "git/meta-freescale" : "748e958db5e8c9cede4186c594a7b5ade314a25a",
    "git/meta-raspberrypi" : "refs/tags/tag_1",
    "git/mbl_manifest" : "refs/heads/manifest_dev_internal_1"
    "git/additional_non_mrr_repo" : "refs/heads/branch_name_2"
}
```
1. The 1st element is an Arm MRR (name prefix with armmbed, and remote is github). It can be found in default.xml manifest file. The new value is a branch ref.
   Before modification to default.xml:
   <project name="armmbed/meta-mbl" path="layers/meta-mbl" remote="github"/>
   After modification:
   <project name="armmbed/meta-mbl" path="layers/meta-mbl" revision="refs/heads/branch_name_1" remote="github"/>
   In this example, script checks that such branch does not exist on remote, creates a  branch from master branch (the default) and push to remote.
2. The 2nd element is a non-Arm MRR. project entry will be modified accordingly, while a hash is acceptable for this pair type.
    No branch will be created, script only checks that such hash exist on remote.
3. The 3rd element is very similar to the 2nd. This time a tag is given ('refs/tags/').
4. The 4th element has the mbl-manifest as a key, which must be in any JSON file. The ref is a branch to create and update the remote.
5. The 5th element is an additional Arm managed repository. A new branch branch_name_2 will be created and pushed to remote. Also, since meta-mbl is given, mbl-linked-repositories.conf will be scanned for the repository name git/additional_non_mrr_repo and updated accordingly with the new branch name branch_name_2 to be linked to from all pointing repositories.
