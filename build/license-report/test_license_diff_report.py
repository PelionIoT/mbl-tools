# Copyright (c) 2019 Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

import license_diff_report as ldr
import pytest
from pathlib import Path
import json

MACHINES = ["imx7d-pico-mbl", "imx7s-warp-mbl"]


@pytest.fixture
def lic_files_to_test():
    manifests = ldr.MANIFESTS
    abspath = Path(__file__).resolve().parent
    output = dict()
    for build_dir in Path(abspath, "test-files").iterdir():
        output[build_dir.name] = dict()
        for machine_dir in build_dir.iterdir():
            pdict = {m: Path(machine_dir, m) for m in manifests}
            output[build_dir.name][machine_dir.name] = pdict
    yield output


@pytest.fixture
def flattened_lic_data(lic_files_to_test):
    output = dict()
    for build_name in lic_files_to_test:
        output[build_name] = {
            m: ldr._from_manifest_json_files(lic_files_to_test[build_name], m)
            for m in ldr.MANIFESTS
        }
    yield output


def test_lics_loaded_and_flattened(flattened_lic_data, lic_files_to_test):
    for build in lic_files_to_test:
        for machine in MACHINES:
            for manifest in ldr.MANIFESTS:
                lic = json.loads(
                    open(
                        str(lic_files_to_test[build][machine][manifest])
                    ).read()
                )
                assert lic.keys() <= flattened_lic_data[build][manifest].keys()


def test_lics_diff_report(flattened_lic_data):
    report, diffs = ldr.flag_diffs(flattened_lic_data, "builda", "buildb")
    assert report
    assert diffs
    for m in ldr.MANIFESTS:
        for pkg in report[m]:
            assert report[m][pkg]["LICENSE STATUS"]


def test_html_report(flattened_lic_data, tmp_path):
    outdir = tmp_path / "html"
    report, diffs = ldr.flag_diffs(flattened_lic_data, "builda", "buildb")
    ldr.make_html(
        report, "mbl-image-development", MACHINES, [str(outdir.resolve())]
    )
    assert diffs
