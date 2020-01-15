#!/usr/bin/env python3

# Copyright (c) 2019, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Parse LAVA results."""

import argparse
from datetime import datetime
from os import environ
import pickle
import sys
import xmlrpc.client

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
.textjob    { font-size: 0.7vw; }
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
</style>
</head>
<body>
"""

HTML_FOOTER = """
</body>
"""

HELP_TEXT = """Lava farm status report generator.
Requires the following environment variables to be set:
  LAVA_SERVER - hostname of the server
  LAVA_USER   - username of login to server
  LAVA_TOKEN  - token used by username to login to server
"""


def main():
    """Perform the main execution."""
    hostname = environ["LAVA_SERVER"]
    try:
        server = connect_to_server(
            environ["LAVA_SERVER"], environ["LAVA_USER"], environ["LAVA_TOKEN"]
        )
    except KeyError as key:
        print("ERROR: unset environment variable - {}".format(key))
        exit(2)

    parser = argparse.ArgumentParser(
        description=HELP_TEXT, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--pickle",
        type=str,
        default="lava-farm-status.pkl",
        nargs=None,
        help="Name of pickle file that contains previous/current status",
    )
    args = parser.parse_args()

    allDevices = server.scheduler.all_device_types()

    try:
        current_queues = server.scheduler.pending_jobs_by_device_type()
    except xmlrpc.client.ProtocolError as e:
        current_queues = None

    print(HTML_HEADER)

    print("<table>")
    print('<col width="250">')
    print('<col width="40">')
    print('<col width="40">')
    print('<col width="40">')
    print('<col width="40">')
    print('<col width="40">')
    print(
        "<tr>"
        "<th>Device Type</th>"
        "<th>Total</th>"
        "<th>Busy</th>"
        "<th>Idle</th>"
        '<th><a href="https://lava.mbedcloudtesting.com/scheduler/labhealth"'
        'target="_blank">Offline</a></th>'
        "<th>Queue</th>"
        "</tr>\n"
    )

    try:
        lastStats = pickle.load(open(args.pickle, "rb"))
    except FileNotFoundError:
        lastStats = []

    stats = []

    totalIdle = 0
    totalBusy = 0
    totalOffline = 0
    totalQueue = 0
    totalDevices = 0

    for device in allDevices:
        numIdle = device["idle"]
        numBusy = device["busy"]
        numOffline = device["offline"]
        total = numIdle + numBusy + numOffline

        if current_queues:
            numQueue = current_queues[device["name"]]
        else:
            numQueue = 0

        totalIdle += numIdle
        totalBusy += numBusy
        totalOffline += numOffline
        totalDevices += total
        totalQueue += numQueue

        stat = {
            "name": device["name"],
            "total": total,
            "busy": numBusy,
            "idle": numIdle,
            "offline": numOffline,
            "queue": numQueue,
        }

        stats.append(stat)

        name = "{}<br>".format(device["name"])

        print(
            "<tr>"
            "<td>{:>23}</td>"
            '<td style="text-align:right">{}</td>'.format(name, total)
        )
        # Print number busy
        print(
            '<td class="{}">{}</td>'.format(
                *get_result_class_and_string(stat, lastStats, "busy")
            )
        )
        # Print number idle
        print(
            '<td class="{}">{}</td>'.format(
                *get_result_class_and_string(stat, lastStats, "idle")
            )
        )
        # Print number offline
        print(
            '<td class="{}">{}</td>'.format(
                *get_result_class_and_string(stat, lastStats, "offline")
            )
        )
        # Print number queue
        print(
            '<td class="{}">{}</td>'.format(
                *get_result_class_and_string(stat, lastStats, "queue")
            )
        )

        print("<tr>")

    print(
        "<tr>"
        "<td>{:>23}</td>"
        '<td style="text-align:right">{}</td>'
        '<td style="text-align:right">{}</td>'
        '<td style="text-align:right">{}</td>'
        '<td style="text-align:right">{}</td>'
        '<td style="text-align:right">{}</td>'
        "</tr>\n".format(
            datetime.now().strftime("Run at %H:%M on %d-%b-%Y"),
            totalDevices,
            totalBusy,
            totalIdle,
            totalOffline,
            totalQueue,
        )
    )

    print("</table>")

    print("<table>")
    print(
        "<tr>"
        "<th>Id</th>"
        "<th>Description - Running Jobs</th>"
        "<th>Start Time</th>"
        "<th>Device Type</th>"
        "<th>Submitter</th>"
        "</tr>\n"
    )

    runningJobs = server.scheduler.jobs.list(
        "RUNNING", None, 0, 100, None, True
    )
    for job in reversed(runningJobs):
        print(
            "<tr>"
            '<td><a href="https://{}/scheduler/job/{}"'
            'target="_blank">{}</a</td>'
            "<td>{}</td>"
            "<td>{}</td>"
            "<td>{}</td>"
            "<td>{}</td>"
            "</tr>".format(
                hostname,
                job["id"],
                job["id"],
                job["description"],
                job["start_time"].split(".")[0],
                job["device_type"],
                job["submitter"],
            )
        )
    print("</table>")

    if totalQueue != 0:
        print("<table>")
        print(
            "<tr>"
            "<th>Id</th>"
            "<th>Description - Queued Jobs</th>"
            "<th>Device Type</th>"
            "<th>Submitter</th>"
            "</tr>\n"
        )

        while totalQueue:

            # scheduler.jobs.list clamps at 100 jobs. Our queue can be bigger
            # than that. So get the data in chuncks of 100 until we have got
            # it all. The jobs are also in descending order of job ID, but
            # we want to show ascending jobID so the eldest queued jobs are
            # at the top of the list.
            if totalQueue > 100:
                skip = totalQueue - 100
                numJobs = 100
            else:
                skip = 0
                numJobs = totalQueue

            queuedJobs = server.scheduler.jobs.list(
                "SUBMITTED", None, skip, numJobs, None, True
            )
            totalQueue -= numJobs
            for queuedJob in reversed(queuedJobs):
                print(
                    "<tr>"
                    '<td><a href="https://{}/scheduler/job/{}"'
                    'target="_blank">{}</a</td>'
                    "<td>{}</td>"
                    "<td>{}</td>"
                    "<td>{}</td>"
                    "</tr>".format(
                        hostname,
                        queuedJob["id"],
                        queuedJob["id"],
                        queuedJob["description"],
                        queuedJob["device_type"],
                        queuedJob["submitter"],
                    )
                )
        print("</table>")

    print(HTML_FOOTER)

    pickle.dump(stats, open(args.pickle, "wb"))


def compare_stats(currrun, laststats, value, show_delta):
    """Compare a value between runs and return indication of better/worse.

    :return: HTML symbol to indicate status.

    """
    result = currrun[value]
    if laststats:
        for stat in laststats:
            if currrun["name"] == stat["name"]:
                result = valueAndSymbol(
                    currrun[value], stat[value], show_delta
                )
                break
    return result


def get_result_class_and_string(currrun, laststats, value):
    """Get a class based on value & the result with comparison indicator.

    :return: Tuple of class - zero_class when zero result, else nonz_class,
    and String with status indicator for HTML.

    """
    result = currrun[value]
    show_delta = False

    if value in ["busy", "idle"]:
        clss = "textblack"
    elif value in ["offline"]:
        if result == 0:
            clss = "textblack"
        else:
            clss = "textred"
    elif value in ["queue"]:
        show_delta = True
        if result == 0:
            clss = "textblack"
        elif result <= 5:
            clss = "textamber"
        else:
            clss = "textred"
    else:
        clss = "textamber"

    if value not in ["offline"]:
        result = "{}".format(
            compare_stats(currrun, laststats, value, show_delta)
        )

    return (clss, result)


def valueAndSymbol(current, last, show_delta):
    """Combine values and symbols."""
    delta = abs(current - last)

    if last < current:
        symbolAndValue = (
            "(&uArr; {}) {}".format(delta, current)
            if show_delta
            else "&uArr; {}".format(current)
        )
    elif last > current:
        symbolAndValue = (
            "(&dArr; {}) {}".format(delta, current)
            if show_delta
            else "&dArr; {}".format(current)
        )
    else:
        symbolAndValue = "&equals;  {}".format(current)
    return symbolAndValue


def connect_to_server(hostname, username, token):
    """Connect to the Lava server.

    :return: server object

    """
    server = xmlrpc.client.ServerProxy(
        "http://%s:%s@%s/RPC2" % (username, token, hostname), allow_none=True
    )
    return server


if __name__ == "__main__":
    sys.exit(main())
