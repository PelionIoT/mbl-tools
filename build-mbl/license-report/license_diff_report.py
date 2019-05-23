#!/usr/bin/env python3
# Copyright (c) 2019 Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause


"""
This script creates a report on the licenses used in an mbl image.

Compares the license.manifest.json files between two builds of mbl for each
machine.

Calls out new and updated licenses.

Flattens the license difference report for all machines into one data
structure.

Generates a log file containing the new and updated licenses that should be
reviewed, along with the associated package names and other metadata.

Optionally generates an HTML report of the complete list of licenses with new
and updated licenses flagged.
"""


import argparse
import json
import os
import pathlib
import re
import sys
import tempfile

from collections import OrderedDict

import artifactory
import jinja2


EXECDIR = pathlib.Path(__file__).resolve().parent

ARTIFACTORY_PREFIX = (
    "https://artifactory.mbed.com/artifactory/isg-mbed-linux/mbed-linux/"
)

MANIFESTS = (
    "image_license.manifest.json",
    "license.manifest.json",
    "initramfs-image_license.manifest.json",
    "initramfs-license.manifest.json",
)

MACHINES = ("raspberrypi3-mbl", "imx7d-pico-mbl", "imx7s-warp-mbl")


def make_html(data, image_name, machines, output_dir):
    """Turn the license data dictionary into an HTML report.

    :param dict data: License data ordered by recipe name.
    """
    for manifest in data:
        for pkg_name in data[manifest]:
            name = "{}_{}_{}.html".format(
                image_name, "_".join(machines), manifest.split(".json")[0]
            )
            env = jinja2.Environment(
                loader=jinja2.FileSystemLoader(str(EXECDIR)),
                autoescape=jinja2.select_autoescape(["html"]),
            )
            template = env.get_template("template.html")
            html_str = template.render(
                title=name,
                license_headers=list(data[manifest][pkg_name].keys()),
                licenses=data[manifest],
            )
            with open(str(pathlib.Path(output_dir, name)), "w") as html_file:
                html_file.write(html_str)
                break


def get_or_download_lics(lic_src, machines, img, apikey=None):
    """Get or download lic data depending on if lic_src is a list of paths.

    If lic_src is a build tag, attempt to get the lic files from Artifactory.
    If lic_src is a list of paths, use those to load the license data.

    :param list lic_src: List of either build tags or license paths.
    :param list machines: List of machines to collect data for.
    :param str img: Image type to collect licenses for.
    :param str apikey: Artifactory apikey (required if lic_src is a build tag).
    """
    if os.path.isdir(lic_src[0]):
        return _make_manifest_dicts(
            _get_local_lics(lic_src, machines, img), MANIFESTS
        )
    else:
        return _make_manifest_dicts(
            _get_lics_from_artifactory(machines, lic_src[0], img, apikey),
            MANIFESTS,
        )


def sort_lics(diffs):
    """Sort the license report data dict.

    Sort by RECIPE NAME and move the sorted data to an OrderedDict.
    """
    sorted_diffs = OrderedDict()
    for manifest in diffs:
        sorted_diffs[manifest] = OrderedDict()
        for key in sorted(
            diffs[manifest].keys(),
            key=lambda x: diffs[manifest][x]["RECIPE NAME"],
        ):
            sorted_diffs[manifest][key] = diffs[manifest][key]
    return sorted_diffs


def flag_diffs(lics, this_build, old_build):
    """Compare the lic data between two builds.

    Add a LICENSE STATUS field to this_build's dict.
    Flag any new or updated licenses.

    Return a tuple containing the report and the diffs as dicts.

    :param dict lics: license data for two builds of mbl.
    :param str this_build: Name of "this_build".
    :param str old_build: Name of "old_build".
    """
    diffs = dict()
    for manifest in MANIFESTS:
        for pkg_name in lics[this_build][manifest]:
            if pkg_name not in lics[old_build][manifest]:
                lics[this_build][manifest][pkg_name]["LICENSE STATUS"] = "NEW"
                diffs[pkg_name] = lics[this_build][manifest][pkg_name][
                    "LICENSE"
                ]
            elif (
                lics[this_build][manifest][pkg_name]["LICENSE"]
                != lics[old_build][manifest][pkg_name]["LICENSE"]
            ):
                lics[this_build][manifest][pkg_name][
                    "LICENSE STATUS"
                ] = "UPDATED"
                diffs[pkg_name] = "{} -> {}".format(
                    lics[old_build][manifest][pkg_name]["LICENSE"],
                    lics[this_build][manifest][pkg_name]["LICENSE"],
                )
            else:
                lics[this_build][manifest][pkg_name][
                    "LICENSE STATUS"
                ] = "UNCHANGED"
    return lics[this_build], diffs


def get_latest_artifactory_build_tag(build_name, current_build_tag, api_key):
    """Get the latest build tag from artifactory."""
    ap = artifactory.ArtifactoryPath(
        ARTIFACTORY_PREFIX, build_name, apikey=api_key
    )
    build_tag_list = sorted(
        (str(p) for p in ap), key=lambda x: int(re.search(r"\d*$", x).group(0))
    )
    # The "last build" tag could actually be the same as the current build
    # when running in our Jenkins pipelines.
    # We should return the penultimate build tag if this is the case.
    last_build_tag = build_tag_list[-1].split("/")[-1]
    penultimate_tag = build_tag_list[-2].split("/")[-1]
    return [
        last_build_tag
        if last_build_tag != current_build_tag
        else penultimate_tag
    ]


class ArtifactoryError(Exception):
    """Artifactory download failed."""


def _set_artifactory_prefix(build_context):
    global ARTIFACTORY_PREFIX
    path = "https://artifactory.mbed.com/artifactory/{context}/mbed-linux/"
    ARTIFACTORY_PREFIX = path.format(context=build_context)
    return build_context


def _download_licenses_json(build_ctx, build_id, machine, img_type, api_key):
    """Construct Artifactory paths and download license files."""
    output_paths = dict()
    for manifest in MANIFESTS:
        ap = os.path.join(
            ARTIFACTORY_PREFIX,
            build_ctx,
            build_id,
            "machine",
            machine,
            "images",
            img_type,
            manifest,
            manifest,
        )
        tgt_path = tempfile.mkdtemp()
        try:
            local_path = _download_from_artifactory(ap, tgt_path, api_key)
            output_paths[manifest] = local_path
        except RuntimeError:
            print("{} not found in Artifactory.".format(ap))
    return output_paths


def _download_from_artifactory(fpath, tgt_path, api_key):
    """Download a single file from Artifactory."""
    lic_file = artifactory.ArtifactoryPath(fpath, apikey=api_key)
    tgt_file = pathlib.Path(tgt_path, os.path.basename(fpath.strip(os.sep)))
    tgt_file.touch(exist_ok=True)
    with open(str(tgt_file), "wb") as local_lfile:
        with lic_file.open() as rem_lfile:
            rbytes = rem_lfile.read()
            local_lfile.write(rbytes)
    return tgt_file.resolve()


def _get_lics_from_artifactory(machines, build_name, img_type, api_key):
    """Get license files from Artifactory."""
    build, *build_id = build_name.split("_")
    lic_paths = dict()
    for machine in machines:
        lic_paths[machine] = _download_licenses_json(
            build, build_name, machine, img_type, api_key
        )
    return lic_paths


def _get_local_lics(paths, machines, images):
    """Get local license paths, validate them and store them in a table.

    Categorise the license file paths by machine and manifest type.

    :param list paths: List of file paths.
    :param list machines: List of known machine types.
    :param list images: List of known image types.
    """
    output_paths = dict()
    for path in paths:
        path = pathlib.Path(path)
        for machine in machines:
            output_paths[machine] = dict()
            for manifest in MANIFESTS:
                output_paths[machine][manifest] = ""
                if all(term in path.parts for term in (machine,)):
                    for f in path.iterdir():
                        if f.name == manifest:
                            output_paths[machine][manifest] = f.resolve()
    return output_paths


def _from_json(filepath):
    """Load a json file to a dictionary."""
    if not filepath:
        return dict()
    with open(str(filepath)) as lic_json_file:
        return json.loads(lic_json_file.read())


def _flatten_dicts(dicts):
    """Flatten an iterable of dicts to a single dict."""
    return {k: v for d in dicts for k, v in d.items()}


def _from_manifest_json_files(lic_file_paths, manifest_type):
    """
    Load a set of license files to a single dict.

    Takes a list of json license file paths and manifest type.
    Returns a flattened dict of all manifest_type licenses for each machine.

    :param dict lic_file_paths: Dictionary of license data {machine:dict(data)}
    :param str manifest_type: type of manifest data loaded.
    :returns dict: dict containing the license data for each machine.
    """
    return _flatten_dicts(
        _from_json(lic_file_paths.get(machine).get(manifest_type))
        for machine in lic_file_paths
    )


def _make_manifest_dicts(lic_paths, manifests):
    return {
        manifest: _from_manifest_json_files(lic_paths, manifest)
        for manifest in manifests
    }


def _parse_args():
    """Parse command line."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "build_tag",
        help=(
            "Build tag of the current build. "
            "Used in the title of the report and used to verify "
            "Artifactory downloads."
        ),
    )
    parser.add_argument(
        "--lics-to-review",
        nargs="+",
        required=True,
        help=(
            "Licenses to review. "
            "Can either be a list of filepaths or an Artifactory build tag."
        ),
    )
    parser.add_argument(
        "--lics-to-compare",
        nargs="+",
        help=(
            "Licenses to compare against. "
            "This can either be a list of filepaths or an Artifactory build "
            "tag."
            "If this option is not given look for the 'last' build in "
            "Artifactory."
        ),
    )
    parser.add_argument(
        "--images",
        nargs="+",
        help=(
            "Images to check licenses for. For example: mbl-image-development."
        ),
    )
    parser.add_argument("--apikey", help="Artifactory API key.")
    parser.add_argument(
        "--html",
        metavar="OUTPUT_DIR",
        help="Output an HTML report at the specified location.",
    )
    parser.add_argument("--machines", nargs="+")
    parser.add_argument(
        "--build-context",
        help=(
            "The build context, e.g. isg-mbed-linux or "
            "isg-mbed-linux-release."
        ),
        default="isg-mbed-linux",
        type=_set_artifactory_prefix,
    )
    return parser.parse_args()


def _main():
    """Script entry point."""
    try:
        args = _parse_args()
        # Keys to refer to the builds in the license dict
        build_review = "buildreview"
        build_cmp = "buildcmp"
        machines = args.machines if args.machines is not None else MACHINES
        machines = [m.strip() for m in machines]
        # split the "build\d*" part from the build tag
        build_name = (
            args.build_tag.split("_")[0]
            if "_" in args.build_tag
            else args.build_tag
        )
        if not args.lics_to_compare[0]:
            # If lics_to_compare is empty use the previous artifactory build
            args.lics_to_compare = get_latest_artifactory_build_tag(
                build_name, args.build_tag, args.apikey
            )
        lics = dict()
        for image in args.images:
            lics[build_review] = get_or_download_lics(
                args.lics_to_review, machines, image.strip(), args.apikey
            )
            lics[build_cmp] = get_or_download_lics(
                args.lics_to_compare, machines, image.strip(), args.apikey
            )
            report, diffs = flag_diffs(lics, build_review, build_cmp)
            sorted_report = sort_lics(report)
            # Create output files if required
            if diffs:
                diff_path = pathlib.Path(
                    args.html[0],
                    image,
                    "{}_diffs.json".format("_".join(machines)),
                )
                diff_path.parent.mkdir(parents=True, exist_ok=True)
                diff_path.touch(exist_ok=True)
                with diff_path.open(mode="w") as diff_file:
                    diff_file.write(json.dumps(diffs))
            if args.html:
                make_html(sorted_report, image, machines, args.html)
    except Exception as err:
        # Don't raise to the interpreter level as this script shouldn't fail
        # even if the license report creation fails.
        print(err, file=sys.stderr)


if __name__ == "__main__":
    sys.exit(_main())
