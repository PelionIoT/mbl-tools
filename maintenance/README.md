## Purpose

This directory contains the tools necessary to:

* Create release branches
* Tag a set of release branches
* Maintain master by cherry-picking from the dev branch

It does this by containing two repo manifests of all the repositories to be maintained in MBL and using the repo tool to check them out and act on them:

* `default.xml` - for the master maintenance (only on master)
* `release.xml` - for the development branch or release branches

It also contains some helper scripts in `scripts`.

Note: Some of the repositories may not be public at this time, as this process is for internal usage at this time.

## Maintenance Directions

Performing a merge of all commits needed from the dev branch into master.

### Set up a maintenance area

Can be done once as a place just to perform all maintenance jobs.

```
mkdir MAINTENANCE
cd MAINTENANCE
# Get the tools on the dev branch - assumed to be the latest versions
git clone git@github:ARMmbed/mbl-tools
export SCRIPTS=$(pwd)/mbl-tools/maintenance/scripts
```

### Start a maintenance job

Set up a new checkout of all the repos we need to maintain, and create a branch for doing the merging.

```
# Get latest tools
cd MAINTENANCE/mbl-tools
git pull
cd ..

# Set up new maintenance repo area
export MAINTDIR=$(pwd)/mbl-maint-20190701
export MAINTBRANCH=jij-maint-20190701

$SCRIPTS/git-sync-start.bash $MAINTDIR
cd $MAINTDIR
 
# Set up new branch
repo start $MAINTBRANCH --all
```

### Check the commits

For each repo, review the commits and cherry-pick those that need to be. Perform any necessary merging on conflicts.
Keep a log of all the commits that could be picked and which ones you didn't pick (and why) and which needed merging/changing.

Some things to watch out for:
* `meta-mbl` - ignore any commits that are changing the `mbl-linked-repositories.conf` for mbl-core
* `mbl-jenkins` - probably ignore any commits that change the `mblPipeline`
* `mbl-core` - double-check that the HEAD of the dev branch is being used by `meta-mbl` - meta-mbl should be fixed before performing the maintenance merge otherwise it will break the automatic tagging below.
* remember to make that list of shas!

```
cd $MAINTDIR/armmbed
 
# Per repo
cd <REPO>
$SCRIPTS/git-sync-diff.bash
git cherry-pick <SHAs>
cd ..
```

### Create the PRs

Create the PRs for each branch:
* Subject: "_target_: sync up with _source_" (e.g.: "master: sync up with warrior-dev");
* Description: put the list of the original commits cherry-picked and the excluded commits if it is the case. You can use the output of the `git-sync-diff.bash` command (from the example above) to make these lists;
* Labels: _sync: dev->master_, _SYNCHRONIZE MERGES_

Only add the original authors of commits if there are problems with the sync, otherwise it is assumed all commits that apply cleanly are ok.

```
# First push all your branches into github
cd $MAINTDIR
repo forall -c git push --set-upstream origin $MAINTBRANCH
 
# Example usage of hub tool to create PRs
# For each PR you will get an opportunity to add PR message - where you include
#  the details of the changes (from the log you kept)
#  See https://hub.github.com/hub-pull-request.1.html for option information
cd armmbed
for i in *; do \
  echo $i; \
  cd $i; \
  hub pull-request -m "master: sync up with warrior-dev" -r github-reviewer -l "sync: dev->master","SYNCHRONIZE MERGES"; \
  cd ..; \
done
```

### Testing

To enable testing you will need to create and push 3 "TEST COMMITS" on:
* `mbl-manifest` - change `default.xml` entries of mbl-config & meta-mbl to your maintenance branches
* `meta-mbl` - change `mbl-linked-repositories.conf` to point your maintenance branch of mbl-core (rather than AUTO-REV)
* `mbl-jenkins` - change `mblPipeline` to point to the maintenance branches for mblToolsBranch, paramsBranch, mblManifestBranch & lavaMblBranch (and any new ones!)

Label the 3 PRs for these repositories as _DO NOT MERGE_, as you will need to back out the TEST COMMIT on each before merging to master.

In Jenkins, change the `mbl-master` job to point to your maintenance branch of `mbl-jenkins`

Perform mbl-master builds on jenkins - edit the description/name to state this is a maintenance test rather than a normal master build

### Merging

Get the PRs reviewed and approved.

__Before merging__:
* Drop the last commits (the TEST COMMITS) on `mbl-manifest`, `meta-mbl` & `mbl-jenkins` and force push. 
* Remove the _DO NOT MERGE_ label from the PR.
* Get re-approval.

___Never "Squash and merge" the commits in any of these PRs!___

Perform the merging using the __"Rebase and merge"__ option.

Finally, change Jenkins `mbl-master` job to point back to the master branch of `mbl-jenkins`.

### Tagging

After the PRs get merged we need to tag the commits in the source and target branches, so that the next diff operation will work.

The format of tags created by the `git-sync-tag.bash` script:
* In the source branch: _source-branch_to_target-branch_ ;
* In the target branch: _source-branch_into_target-branch_ .

```
cd $MAINTDIR
 
# NOTE: Do not have any modified files in the repos otherwise this operation will fail;
#       and the repos must be the same ones you created the PRs from and have not been updated
#       (i.e. no repo sync or git fetch/pull operations)
repo forall -c $SCRIPTS/git-sync-tag.bash
```

## Releasing directions

### Release on default dev branch:
```
mkdir my-workdir ; cd my-workdir
git clone git@github.com:ARMmbed/mbl-tools
mbl-tools/maintenance/scripts/git-sync-start.bash --release my-release
```

### Release tagging on release branch x.y:
```
mkdir my-workdir ; cd my-workdir
git clone git@github.com:ARMmbed/mbl-tools -b mbl-os-x.y
mbl-tools/maintenance/scripts/git-sync-start.bash --release my-release
```

