#!/usr/bin/env python3

# Copyright (c) 2019, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Parse LAVA results."""

import argparse
import sys
import xmlrpc.client
import yaml


outputBuffer = []


def connect_to_server(hostname, username, token):
    """Connect to the Lava server.

    :return: server object

    """
    server = xmlrpc.client.ServerProxy(
        "http://%s:%s@%s/RPC2" % (username, token, hostname), allow_none=True
    )
    return server


def setup_parser():
    """Create command line parser.

    :return: parser object.

    """
    parser = argparse.ArgumentParser(description="Extract Lava Results")
    parser.add_argument(
        "--server",
        type=str,
        default="lava.mbedcloudtesting.com",
        nargs="?",
        help="Lava server name",
    )
    parser.add_argument(
        "--user", type=str, nargs="?", help="Lava username", required=True
    )
    parser.add_argument(
        "--token", type=str, nargs="?", help="Lava API token", required=True
    )
    parser.add_argument(
        "--tag",
        type=str,
        default="mbl-os-0.6.1-rc2_build2",
        nargs="?",
        help="Build tag",
    )
    parser.add_argument(
        "--numResults",
        type=int,
        default="100",
        nargs="?",
        help="Number of Results",
    )
    parser.add_argument(
        "--submitter", type=str, default="mbl", nargs="?", help="Submitter"
    )
    parser.add_argument(
        "--lava_query", type=str, default="", nargs="?", help="Lava Query"
    )
    parser.add_argument(
        "--sort", type=str, default="", nargs="?", help="Sort type"
    )
    parser.add_argument(
        "--query_owner",
        type=str,
        default="",
        nargs="?",
        help="Lava query owner",
    )
    parser.add_argument(
        "--fail",
        type=str,
        default="false",
        nargs="?",
        help="Set to true to show only failed results",
    )
    return parser


def get_testjob_suites_list(server, id):
    """Get lava suites of test job id.

    :return: dictionary of suites.

    """
    return yaml.load(
        server.results.get_testjob_suites_list_yaml(id), yaml.BaseLoader
    )


def get_testsuite_results(server, id, name):
    """Get lava results of test suite in job id.

    :return: dictionary of results.

    """
    return yaml.load(
        server.results.get_testsuite_results_yaml(id, name), yaml.BaseLoader
    )


def print_result(result, server, hostname, show_failures_only):
    """Print out the test jobs results as html output."""
    tempBuffer = []
    failure_detected = False

    if server.scheduler.job_details(result["id"])["status"] != "Complete":
        failure_detected = True
        color = "red"
    else:
        color = "black"

    tempBuffer.append("<table>")
    tempBuffer.append('<col width="350">')
    tempBuffer.append('<col width="150">')
    tempBuffer.append('<col width="100">')
    tempBuffer.append('<col width="100">')
    tempBuffer.append('<col width="100">')

    try:
        worker = server.scheduler.devices.show(result["actual_device_id"])[
            "worker"
        ].split(".")[0]
    except xmlrpc.client.Fault as e:
        worker = "nowhere"

    tempBuffer.append(
        "<br><b>{} on {}</b>\n".format(
            result["description"], result["requested_device_type_id"]
        )
    )

    tempBuffer.append(
        'Job <a href="https://{}/scheduler/job/{}">{}</a> Status: <font color="{}">{}</font> on device <i>{}</i>, worker <i>{}</i>. Submitted by <i>{}</i> \n'.format(  # noqa: E501
            hostname,
            result["id"],
            result["id"],
            color,
            server.scheduler.job_details(result["id"])["status"],
            result["actual_device_id"],
            worker,
            server.scheduler.job_details(result["id"])["submitter_username"],
        )
    )

    tempBuffer.append("<tr></tr>")

    tempBuffer.append(
        "<tr><th>Suite</th><th>Number Of Tests</th><th>Pass</th><th>Fail</th><th>Skip</th></tr>\n"  # noqa: E501
    )

    suites = get_testjob_suites_list(server, result["id"])

    for suite in suites:
        numberOfTests = 0
        numberOfPasses = 0
        numberOfFails = 0
        numberOfSkips = 0

        if suite["name"] != "lava":
            test_results = get_testsuite_results(
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
                    failure_detected = True
                else:
                    tempBuffer.append(item)
            if numberOfSkips == 0:
                skipColor = "black"
            else:
                skipColor = "orange"
            if numberOfFails == 0:
                failColor = "black"
            else:
                failColor = "red"

            tempBuffer.append(
                '<tr><td>{}</td><td>{}</td><td>{}</td><td><font color="{}">{}</font></td><td><font color="{}">{}</font></td><tr>'.format(  # noqa: E501
                    suite["name"],
                    numberOfTests,
                    numberOfPasses,
                    failColor,
                    numberOfFails,
                    skipColor,
                    numberOfSkips,
                )
            )
    tempBuffer.append("</table>")

    if show_failures_only is True:
        if failure_detected is True:
            for line in tempBuffer:
                outputBuffer.append(line)
    else:
        for line in tempBuffer:
            outputBuffer.append(line)


def sortResultsByDevice(results):
    """Sort the lava test jobs by device.

    :return: sorted list

    """
    sortedResults = sorted(
        results,
        key=lambda i: (i["requested_device_type_id"], i["description"]),
    )
    return sortedResults


def get_custom_query(server, submitter, tag):
    """Get lava query for test jobs associated with tag.

    :return: query string

    """
    if submitter == "wild":
        test_tag = ""
    else:
        test_tag = "testjob__submitter__exact__" + submitter + ","

    # If the tag contains -1 then find the first matching job that contains
    # the build information, less the version number, and then find all of
    # them containing that version.
    # Otherwise just use the tag provided.
    if tag.find("-1") != -1:
        # Keep the tag up to the "-1"
        test_tag2 = (
            "testjob__description__contains__" + tag[0 : tag.find("-1")]
        )
        results = server.results.make_custom_query(
            "testjob", test_tag + test_tag2, 1
        )
        if len(results) != 0:
            test_tag2 = (
                "testjob__description__contains__"
                + results[0]["description"].split()[0]
            )
    else:
        test_tag2 = "testjob__description__contains__" + tag

    return test_tag + test_tag2


def main():
    """Perform the main execution."""
    # Parse command line
    options = setup_parser().parse_args()

    server = connect_to_server(options.server, options.user, options.token)

    if options.lava_query == "":
        # Find results from jobs submitted by mbl and containing the provided
        # build tag
        query = get_custom_query(server, options.submitter, options.tag)
        results = server.results.make_custom_query(
            "testjob", query, options.numResults
        )
    else:
        try:
            results = server.results.run_query(
                options.lava_query, options.numResults, options.query_owner
            )
        except xmlrpc.client.Fault as e:
            outputBuffer.append(
                'Error running Lava query "{}"<br>'.format(options.lava_query)
            )
            results = []

    if options.sort == "by_device":
        results = sortResultsByDevice(results)

    no_failures_found = True
    show_failures_only = options.fail == "true"

    outputBuffer.append("<head>")
    outputBuffer.append("<style>")
    outputBuffer.append("table, th, td {")
    outputBuffer.append("border: 1px solid black;")
    outputBuffer.append("border-collapse: collapse;")
    outputBuffer.append("}")
    outputBuffer.append("</style>")
    outputBuffer.append("</head>")
    outputBuffer.append("<body>")

    if options.lava_query == "":
        outputBuffer.append(
            '{} results found for submitter "{}" and build "{}"<br>'.format(
                len(results), options.submitter, options.tag
            )
        )
    else:
        outputBuffer.append(
            '{} results found for lava query "{}" <br>'.format(
                len(results), options.lava_query
            )
        )

    for result in results:
        # print(result)
        # print(result['requested_device_type_id'])
        # print(result['definition'])
        # print(result['id'])
        # print(server.results.get_testjob_results_yaml(result['id']))
        # print(server.results.get_testjob_suites_list_yaml(result['id']))

        no_failures_found = False
        print_result(result, server, options.server, show_failures_only)

    if show_failures_only and no_failures_found:
        if options.lava_query == "":
            outputBuffer.append(
                'No matching failure results found for submitter "{}" and build "{}"'.format(  # noqa: E501
                    options.submitter, options.tag
                )
            )
        else:
            outputBuffer.append(
                'No matching failure results found for lava query "{}" <br>'.format(  # noqa: E501
                    options.lava_query
                )
            )

    outputBuffer.append("</body>")

    for line in outputBuffer:
        print(line)


if __name__ == "__main__":
    sys.exit(main())
