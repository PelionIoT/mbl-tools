#!/usr/bin/env python3

# Copyright (c) 2019, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Create daily LAVA report."""

import lavaResultExtract as lRE
import sys
from os import environ
import argparse

HELP_TEXT = """Lava daily report generator.
Requires the following environment variables to be set:
  LAVA_SERVER - hostname of the server
  LAVA_USER   - username of login to server
  LAVA_TOKEN  - token used by username to login to server
  REPORT_LINK - URL of Lava report generation script
"""

HTML_HEADER = """
<head>
<style>
body { background-color: black; }
table, th, td {
    border:1px solid #669999;
    border-collapse: collapse;
    font-size: 1.5vw;
    font-family: Arial, Helvetica, sans-serif;
    font-weight: bold;
    padding:5px;
    text-shadow:1px 1px 1px #333333;
    border-bottom:3px solid #669999;
    background-color:#bbbbbb;
}
table { min-width: 100%; }
th { color:#353531; text-shadow:1px 1px 1px #666666; }
.backamber  { background-color:#804d00; }
.backred    { background-color:#8b0000; }
.backgreen  { background-color:#006400; }
.backgrey   { background-color:#808080; }
.textbuild  { font-size: 2vw; }
.textred    { color: #8b0000; text-align: right; text-shadow:1px 1px 1px #aa6666; }
.textamber  { color: #804d00; text-align: right; text-shadow:1px 1px 1px #aa9966; }
.textgreen  { color: #006400; text-align: right; text-shadow:1px 1px 1px #66aa66; }
.textblack  { color: #353531; text-align: right; text-shadow:1px 1px 1px #666666; }
.textboard  { font-size: 1vw; }
.row { display: flex; }
.column { flex: 50%; }
a:link { text-decoration: none; color:#fff; }
a:visited { text-decoration: none; color:#fff; }
a:hover { text-decoration: underline; }
a:active { text-decoration: underline; }
</style>
</head>
<body>
"""

HTML_FOOTER = """
</body>
"""


def get_results_summary(server, submitter, build_name):
    """Get a summary of the jobs/tests for a build.

    :return: Summary dictionary

    """
    # Get test jobs for the given jenkins build_name
    query = lRE.get_custom_query(
        server, submitter, "{}_build-1".format(build_name)
    )
    results = server.results.make_custom_query("testjob", query, 100)
    build_num = query[query.rfind("build") :]

    summary = {
        "Name": build_name,
        "Build": build_num,
        "Totals": {},
        "Boards": {},
    }
    summary["Totals"] = {
        "Jobs": len(results),
        "Complete": 0,
        "Pending": 0,
        "Suites": 0,
        "Failed": 0,
        "Passed": 0,
    }

    for result in results:
        # print( result['id'] )

        board = result["requested_device_type_id"]
        if board not in summary["Boards"]:
            summary["Boards"][board] = {
                "Jobs": 0,
                "Complete": 0,
                "Pending": 0,
                "Suites": 0,
                "Failed": 0,
                "Passed": 0,
            }

        details = server.scheduler.job_details(result["id"])
        if details["status"] == "Complete":
            summary["Boards"][board]["Complete"] += 1
            summary["Totals"]["Complete"] += 1
        elif details["status"] != "Incomplete":
            summary["Boards"][board]["Pending"] += 1
            summary["Totals"]["Pending"] += 1

        summary["Boards"][board]["Jobs"] += 1

        suites = lRE.get_testjob_suites_list(server, result["id"])

        for suite in suites:
            numberOfTests = 0
            numberOfPasses = 0
            numberOfFails = 0
            numberOfSkips = 0

            if suite["name"] != "lava":
                summary["Boards"][board]["Suites"] += 1
                summary["Totals"]["Suites"] += 1
                test_results = lRE.get_testsuite_results(
                    server, result["id"], suite["name"]
                )
                for item in test_results:
                    numberOfTests += 1
                    if item["result"] == "pass":
                        numberOfPasses += 1
                    elif item["result"] == "skip":
                        numberOfSkips += 1
                    elif item["result"] == "fail":
                        numberOfFails += 1
                summary["Totals"]["Failed"] += numberOfFails
                summary["Totals"]["Passed"] += numberOfPasses
                summary["Boards"][board]["Failed"] += numberOfFails
                summary["Boards"][board]["Passed"] += numberOfPasses

    return summary


def choose_class(result, zero_class, nonz_class):
    """Return one of the classes based on the result.

    :return: zero_class when zero result, else nonz_class

    """
    if result == 0:
        return zero_class
    else:
        return nonz_class


def html_output(results, link, submitter):
    """Print out all the summary results in HTML tables."""
    print(HTML_HEADER)

    print('<div class="row">')
    half = int((len(results) + 1) / 2)
    count = 0
    print('<div class="column">')
    for result in results:
        if count == half:
            print("</div>")  # Finish the col
            print('<div class="column">')
        count += 1
        failed = (
            result["Totals"]["Jobs"]
            - result["Totals"]["Complete"]
            - result["Totals"]["Pending"]
        )
        if result["Totals"]["Jobs"] > 0:
            if failed == 0 and result["Totals"]["Failed"] == 0:
                backclass = "backgreen"
            elif (
                result["Totals"]["Complete"] == 0
                and result["Totals"]["Failed"] == 0
            ):
                backclass = "backred"
            else:
                backclass = "backamber"
        else:
            backclass = "backgrey"

        anchor = "{}?image_version={}&image_number={}&submitter={}".format(
            link, result["Name"], result["Build"][5:], submitter
        )

        print("<table><tr>")
        print(
            '<th class="textbuild {}" colspan="5"><a href="{}">{} {}</a></th>'.format(  # noqa: E501
                backclass, anchor, result["Name"], result["Build"]
            )
        )
        print("</tr><tr>")
        if result["Totals"]["Pending"] > 0:
            print("<th>Jobs (pending)</th>")
            print(
                '<td class="textamber">{}</td>'.format(
                    result["Totals"]["Pending"]
                )
            )
            span = "1"
        else:
            print("<th>Jobs</th>")
            span = "2"
        print(
            '<td class="{}" colspan="{}">{}</td>'.format(
                choose_class(
                    result["Totals"]["Complete"], "textblack", "textgreen"
                ),
                span,
                result["Totals"]["Complete"],
            )
        )
        print(
            '<td class="{}" colspan="2">{}</td>'.format(
                choose_class(failed, "textblack", "textred"), failed
            )
        )
        print("</tr><tr>")
        print("<th>Tests</th>")
        print(
            '<td class="{}" colspan="2">{}</td>'.format(
                choose_class(
                    result["Totals"]["Passed"], "textblack", "textgreen"
                ),
                result["Totals"]["Passed"],
            )
        )
        print(
            '<td class="{}" colspan="2">{}</td>'.format(
                choose_class(
                    result["Totals"]["Failed"], "textblack", "textred"
                ),
                result["Totals"]["Failed"],
            )
        )
        for board, info in result["Boards"].items():
            print("</tr><tr>")
            print('<th class="textboard">{} (jobs/tests)</th>'.format(board))
            print(
                '<td class="textboard {}">{}</td>'.format(
                    choose_class(info["Complete"], "textblack", "textgreen"),
                    info["Complete"],
                )
            )
            failed = info["Jobs"] - info["Complete"] - info["Pending"]
            print(
                '<td class="textboard {}">{}</td>'.format(
                    choose_class(failed, "textblack", "textred"), failed
                )
            )
            print(
                '<td class="textboard {}">{}</td>'.format(
                    choose_class(info["Passed"], "textblack", "textgreen"),
                    info["Passed"],
                )
            )
            print(
                '<td class="textboard {}">{}</td>'.format(
                    choose_class(info["Failed"], "textblack", "textred"),
                    info["Failed"],
                )
            )
        print("</tr></table>")
    print("</div>")  # Finish the col
    print("</div>")  # Finish the row
    print(HTML_FOOTER)


def main():
    """Create the daily report."""
    parser = argparse.ArgumentParser(
        description=HELP_TEXT, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--submitter",
        type=str,
        default="mbl",
        nargs=None,
        help="Submitter (default: mbl)",
    )
    parser.add_argument(
        "build_name", nargs="+", help="List of build names from jenkins"
    )
    args = parser.parse_args()

    try:
        server = lRE.connect_to_server(
            environ["LAVA_SERVER"], environ["LAVA_USER"], environ["LAVA_TOKEN"]
        )
        link = environ["REPORT_LINK"]
    except KeyError as key:
        print("ERROR: unset environment variable - {}".format(key))
        exit(2)

    results = []
    for build in args.build_name:
        results.append(get_results_summary(server, args.submitter, build))

    html_output(results, link, args.submitter)


if __name__ == "__main__":
    sys.exit(main())
