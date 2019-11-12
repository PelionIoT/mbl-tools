#!/usr/bin/env python3

# Copyright (c) 2019, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Create daily LAVA report."""

import lavaResultExtract as lRE
import sys
from os import environ
import argparse
from datetime import datetime

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
    font-size: 1.3vw; /* Default size (jobs/tests) */
    font-family: Arial, Helvetica, sans-serif;
    font-weight: bold;
    padding:5px;
    border-bottom:3px solid #669999;
    background-color:#f2f2f2;
}
table { min-width: 100%; }
th { color:#353531; }
.backamber  { background-color:#cc7a00; color:#fff; }
.backred    { background-color:#8b0000; color:#fff; }
.backgreen  { background-color:#006400; color:#fff; }
.backgrey   { background-color:#808080; color:#fff; }
.textbuild  { font-size: 2vw; } /* Build job header size */
.textboard  { font-size: 0.9vw; } /* Board results size */
.texttime   { float: right; font-size: 0.8vw; color:#fff }
.textkey    { background-color:#000; color:#fff; font-size: 0.9vw; }
.textred    { color: #e60000; text-align: right; }
.textamber  { color: #e68a00; text-align: right; }
.textgreen  { color: #009900; text-align: right; }
.textblack  { color: #353531; text-align: right; }
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

MAX_RESULTS = 100


def get_relative_time(timestamp):
    """Given a timestamp string, get a relative time.

    :return: Human readable relative time.

    """
    dt = datetime.strptime(timestamp, "%Y%m%dT%H:%M:%S")
    delta = datetime.now() - dt
    days = delta.days
    relative = ""
    if days != 0:
        relative = "{} day{} ago".format(days, ("" if days == 1 else "s"))
    else:
        mins = int(delta.seconds / 60)
        if mins < 100:
            relative = "{} min{} ago".format(mins, ("" if mins == 1 else "s"))
        else:
            hours = int(delta.seconds / 3600)
            relative = "{} hour{} ago".format(
                hours, ("" if hours == 1 else "s")
            )
    return relative


def get_results_summary(server, submitter, build_name, build_num=-1):
    """Get a summary of the jobs/tests for a build.

    :return: Summary dictionary

    """
    # Get test jobs for the given jenkins build_name
    query = lRE.get_custom_query(
        server, submitter, "{}_build{}".format(build_name, build_num)
    )
    results = server.results.make_custom_query("testjob", query, MAX_RESULTS)
    build_num = query[query.rfind("build") + 5 :]

    if len(results) > 0:
        time = get_relative_time(results[0]["submit_time"].value)
    else:
        time = "never"

    summary = {
        "Name": build_name,
        "Build": build_num,
        "Totals": {},
        "Boards": {},
        "Time": time,
    }
    summary["Totals"] = {
        "Jobs": len(results),
        "Complete": 0,
        "Pending": 0,
        "Incomplete": 0,
        "Suites": 0,
        "Failed": 0,
        "Passed": 0,
    }

    for result in results:
        board = result["requested_device_type_id"]
        if board not in summary["Boards"]:
            summary["Boards"][board] = {
                "Jobs": 0,
                "Complete": 0,
                "Pending": 0,
                "Incomplete": 0,
                "Suites": 0,
                "Failed": 0,
                "Passed": 0,
            }

        details = server.scheduler.job_details(result["id"])
        if details["status"] == "Complete":
            summary["Boards"][board]["Complete"] += 1
            summary["Totals"]["Complete"] += 1
        elif details["status"] in ["Incomplete", "Canceled"]:
            summary["Boards"][board]["Incomplete"] += 1
            summary["Totals"]["Incomplete"] += 1
        else:
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


# List of indicators based for jobs, tests and overall
# Format for each list entry is:
# [{"Type": threshold ...}, [positive sym, negative sym, desc]]
INDICATORS = [
    [{"Jobs": 0, "Tests": 0, "All": 0}, ["equals", "equals", "Same"]],
    [{"Jobs": 1, "Tests": 2, "All": 5}, ["#8673", "#8675", "Trivial"]],
    [{"Jobs": 3, "Tests": 5, "All": 10}, ["uArr", "dArr", "Minor"]],
    [{"Jobs": 7, "Tests": 10, "All": 20}, ["#10506", "#10507", "Major"]],
    [{"Jobs": 0, "Tests": 0, "All": 0}, ["#10224", "#10225", "Serious"]],
]


def get_indicator(value, last, prev):
    """Return an indicator of much different the last and prev results are.

    :return: HTML symbol to indicate how much difference.

    """
    if value in ["Complete", "Incomplete"]:
        ind_type = "Jobs"
    elif value in ["Passed", "Failed"]:
        ind_type = "Tests"
    else:
        ind_type = "All"

    diff = abs(last - prev)
    index = 0 if last > prev else 1
    for group in INDICATORS:
        threshold = group[0][ind_type]
        indicator = group[1][index]
        if threshold >= diff:
            break
    # Return the last one found
    return "&{};".format(indicator)


def indicator_key_table():
    """Print out a simple key table of indicators."""
    print("<table><tr>")
    for group in INDICATORS:
        print(
            '<td class="textkey">&{}; {}</td>'.format(group[1][0], group[1][2])
        )
    print("</tr></table>")


def compare_runs(runs, value, board=None):
    """Compare a value between runs and return indication of better/worse.

    :return: HTML symbol to indicate status.

    """
    if "Previous" in runs:
        if board:
            last = runs["Last"]["Boards"][board][value]
            if board in runs["Previous"]["Boards"]:
                prev = runs["Previous"]["Boards"][board][value]
            else:
                # Can't compare as board didn't get run last time
                return ""
        else:
            last = runs["Last"]["Totals"][value]
            prev = runs["Previous"]["Totals"][value]
        return "{} ".format(get_indicator(value, last, prev))
    else:
        return ""


def choose_class(result, zero_class, nonz_class):
    """Return one of the classes based on the result.

    :return: zero_class when zero result, else nonz_class

    """
    if result == 0:
        return zero_class
    else:
        return nonz_class


def get_result_class_and_string(runs, value, board=None):
    """Get a class based on value & the result with comparison indicator.

    :return: Tuple of class - zero_class when zero result, else nonz_class,
    and String with status indicator for HTML.

    """
    if board:
        result = runs["Last"]["Boards"][board][value]
    else:
        result = runs["Last"]["Totals"][value]

    if value in ["Complete", "Passed"]:
        clss = choose_class(result, "textblack", "textgreen")
    elif value in ["Incomplete", "Failed"]:
        clss = choose_class(result, "textblack", "textred")
    else:
        clss = "textamber"

    result = "{}{}".format(compare_runs(runs, value, board), result)
    return (clss, result)


# How much complete/incomplete jobs are worth compared to passed/failed tests
JOBS_FACTOR = 5


def calculate_overall(totals):
    """Get an overall value from a dictionary of run totals.

    :return: Overall value.

    """
    result = totals["Complete"] - totals["Incomplete"]
    result *= JOBS_FACTOR
    result += totals["Passed"] - totals["Failed"]
    return result


def get_result_overall_class_and_string(runs):
    """Get a class based on value & the result with comparison indicator.

    :return: Tuple of class and String with status indicator for HTML.

    """
    totals = runs["Last"]["Totals"]
    if "Previous" in runs:
        last = calculate_overall(totals)
        prev = calculate_overall(runs["Previous"]["Totals"])
        indicator = " {}".format(get_indicator("All", last, prev))
    else:
        last = 0
        prev = 0
        indicator = ""

    if totals["Jobs"] > 0:
        if totals["Incomplete"] == 0 and totals["Failed"] == 0:
            # Complete success!
            backclass = "backgreen"
        elif last < prev:
            # Things are getting worse!
            backclass = "backred"
        else:
            # Still some problems, but probably getting better.
            backclass = "backamber"
    else:
        # Nothing ran
        backclass = "backgrey"

    return (backclass, indicator)


def html_output(results, link, submitter):
    """Print out all the summary results in HTML tables."""
    print(HTML_HEADER)

    print('<div class="row">')
    half = int((len(results) + 1) / 2)
    count = 0
    print('<div class="column">')
    for runs in results:
        result = runs["Last"]
        # Put half the jobs in one column and the others in another
        if count == half:
            print("</div>")  # Finish the col
            print('<div class="column">')
        count += 1

        # Work out the heading colour based on results
        (backclass, indicator) = get_result_overall_class_and_string(runs)

        # Quick link to the detailed results
        anchor = "{}?image_version={}&image_number={}&submitter={}".format(
            link, result["Name"], result["Build"], submitter
        )

        # Start the table with a main job name heading
        print("<table><tr>")
        header = '<span class="textbuild"><a href="{}">{} build{}</a></span>'.format(  # noqa: E501
            anchor, result["Name"], result["Build"]
        )
        header = '{}{}<span class="texttime">{}</span>'.format(
            header, indicator, result["Time"]
        )
        print('<th class="{}" colspan="5">{}</th>'.format(backclass, header))
        print("</tr><tr>")
        # Indicate there are still jobs pending
        if result["Totals"]["Pending"] > 0:
            print("<th>Jobs (pending)</th>")
            span = "1"
        else:
            if (
                "Previous" in runs
                and runs["Previous"]["Totals"]["Pending"] > 0
            ):
                print("<th>Jobs (previous pends)</th>")
                span = "1"
            else:
                print("<th>Jobs</th>")
                span = "2"
        if span == "1":
            print(
                '<td class="{}">{}</td>'.format(
                    *get_result_class_and_string(runs, "Pending")
                )
            )

        # Overall job stats
        print(
            '<td colspan="{}" class="{}">{}</td>'.format(
                span, *get_result_class_and_string(runs, "Complete")
            )
        )
        print(
            '<td colspan="2" class="{}">{}</td>'.format(
                *get_result_class_and_string(runs, "Incomplete")
            )
        )
        print("</tr><tr>")
        # Overall test stats
        print("<th>Tests</th>")
        print(
            '<td colspan="2" class="{}">{}</td>'.format(
                *get_result_class_and_string(runs, "Passed")
            )
        )
        print(
            '<td colspan="2" class="{}">{}</td>'.format(
                *get_result_class_and_string(runs, "Failed")
            )
        )
        # Per board stats
        for board, info in result["Boards"].items():
            print("</tr><tr>")
            print('<th class="textboard">{} (jobs/tests)</th>'.format(board))
            print(
                '<td class="textboard {}">{}</td>'.format(
                    *get_result_class_and_string(runs, "Complete", board)
                )
            )
            print(
                '<td class="textboard {}">{}</td>'.format(
                    *get_result_class_and_string(runs, "Incomplete", board)
                )
            )
            print(
                '<td class="textboard {}">{}</td>'.format(
                    *get_result_class_and_string(runs, "Passed", board)
                )
            )
            print(
                '<td class="textboard {}">{}</td>'.format(
                    *get_result_class_and_string(runs, "Failed", board)
                )
            )
        print("</tr></table>")
    indicator_key_table()
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
        runs = {}
        runs["Last"] = get_results_summary(server, args.submitter, build)
        if runs["Last"]["Build"]:
            build_num = int(runs["Last"]["Build"]) - 1
            if build_num > 0:
                runs["Previous"] = get_results_summary(
                    server, args.submitter, build, build_num
                )
        results.append(runs)

    html_output(results, link, args.submitter)


if __name__ == "__main__":
    sys.exit(main())
