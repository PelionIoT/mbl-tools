#!/usr/bin/env python3

# Copyright (c) 2017, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Submit to LAVA application.

This application is responsible to submit jobs to LAVA.
"""
import enum
import argparse
import logging
import sys
import os
import time
import xmlrpc.client
import urllib

import jinja2
import yaml


default_template_base_path = "lava-job-definitions"

valid_device_types = (
    "bcm2837-rpi-3-b-32",
    "bcm2837-rpi-3-b-plus-32",
    "imx7s-warp-mbl",
    "imx7d-pico-mbl",
    "imx8mmevk-mbl",
    "imx6ul-pico-mbl",
)

black_list_images = {
    "mbl-image-production": [
        "bcm2837-rpi-3-b-32",
        "bcm2837-rpi-3-b-plus-32",
        "imx8mmevk-mbl",
    ]
}


class ExitCode(enum.Enum):
    """Application return codes."""

    SUCCESS = 0
    CTRLC = 1
    ERROR = 2


class JobStatusCode(enum.Enum):
    """Job status codes."""

    SUCCESS = 0
    NOT_FINISHED = 1
    FAILURE = 2


class LAVATemplates(object):
    """LAVA templates class."""

    def __init__(self, template_path, lava_template_names, dry_run):
        """Initialise LAVATemplates class."""
        self.template_path = template_path
        self.lava_template_names = lava_template_names
        self.dry_run = dry_run

    def process(
        self,
        image_url,
        build_tag,
        build_url,
        mbl_branch,
        mbl_revisions,
        pipeline_data,
        notify_user,
        notify_emails,
        device_type,
        callback_domain,
        callback_port,
        treasure_database,
    ):
        """Process templates rendering them with the right values."""
        lava_jobs = []
        for template_name in self.lava_template_names:
            template = self._load_template(template_name)
            lava_job = template.render(
                image_url=image_url,
                build_tag=build_tag,
                build_url=build_url,
                mbl_branch=mbl_branch,
                mbl_revisions=mbl_revisions,
                pipeline_data=pipeline_data,
                notify_user=notify_user,
                notify_emails=notify_emails,
                device_type=device_type,
                callback_domain=callback_domain,
                callback_port=callback_port,
                treasure_database=treasure_database,
                tags={},
            )
            lava_jobs.append(lava_job)
            if self.dry_run:
                self._dump_job(lava_job, device_type, template_name)
        return lava_jobs

    def _dump_job(self, job, device_type, template_name):
        """Dump LAVA job into yaml files under tmp/ directory structure."""
        output_path = "tmp"
        testpath = os.path.join(output_path, device_type, template_name)
        logging.info("Dumping job data into {}".format(testpath))
        if not os.path.exists(os.path.dirname(testpath)):
            os.makedirs(os.path.dirname(testpath))
        with open(testpath, "w") as f:
            f.write(job)

    def _load_template(self, template_name):
        """Return a jinja2 template starting from a yaml file on disk."""
        try:
            if template_name:
                template_full_path = os.path.join(
                    self.template_path, "testplans"
                )
                template_loader = jinja2.FileSystemLoader(
                    searchpath=[template_full_path, self.template_path]
                )
                template_env = jinja2.Environment(
                    loader=template_loader,
                    trim_blocks=True,
                    lstrip_blocks=True,
                )
                template = template_env.get_template(template_name)
        except jinja2.exceptions.TemplateNotFound as e:
            raise Exception(
                "Cannot find template {} in {}".format(
                    template_name, template_full_path
                )
            )
        return template


class LAVAServer(object):
    """LAVA server class."""

    def __init__(self, server_url, username, token, dry_run):
        """Initialise LAVAServer class."""
        self.base_url = self._normalise_url(server_url)
        self.api_url = self._get_api_url(username, token)
        self.job_info_url = self._get_job_info_url()
        self.connection = self._connect()
        self.dry_run = dry_run

    def submit_job(self, job):
        """Submit a job to LAVA.

        This function returns an XML-RPC integer which is the newly created
        job's id, provided the user is authenticated with an username and
        token. If the job is a multinode job, this function returns the list of
        created job IDs.
        """
        job_ids = []
        if self.dry_run:
            logging.warning("Job not submitted (--dry-run passed)")
        else:
            jobs = self.connection.scheduler.submit_job(job)
            if isinstance(jobs, int):
                job_ids = [jobs]
            else:
                job_ids = jobs
            logging.debug("Job(s) submitted: {}".format(job_ids))
        return job_ids

    def get_job_urls(self, job_ids):
        """Given a list of job IDs, return their full urls."""
        lava_job_urls = []
        for job_id in job_ids:
            lava_job_urls.append(self.job_info_url.format(job_id))
        return lava_job_urls

    def check_job_status(self, job_id):
        """Given a job ID, return its status (waiting, passed, failed)."""
        return_value = JobStatusCode.SUCCESS.value
        results = yaml.safe_load(
            self.connection.results.get_testjob_results_yaml(job_id)
        )
        if len(results) == 0:
            return JobStatusCode.NOT_FINISHED.value
        for result in results:
            if result["result"] != "pass":
                logging.error("Test case %s failed", result["id"])
                return_value = JobStatusCode.FAILURE.value
        return return_value

    def _connect(self):
        """Create a xmlrpc client using LAVA url API."""
        try:
            connection = xmlrpc.client.ServerProxy(self.api_url)
            logging.debug("Connected to LAVA: {}".format(connection))
        except (xmlrpc.client.ProtocolError, xmlrpc.client.Fault) as e:
            raise e
        return connection

    def _normalise_url(self, server_url):
        """Return LAVA base url."""
        if not (
            server_url.startswith("http://")
            or server_url.startswith("https://")
        ):
            server_url = "https://{}".format(server_url)
        logging.debug("Base LAVA url: {}".format(server_url))
        return server_url

    def _get_api_url(self, username, token):
        """Return LAVA API url."""
        url = urllib.parse.urlsplit(self.base_url)
        api_url = "{}://{}:{}@{}/RPC2".format(
            url.scheme, username, token, url.netloc
        )
        logging.debug("API LAVA url: {}".format(api_url))
        return api_url

    def _get_job_info_url(self):
        """Return LAVA base url for job details."""
        url = urllib.parse.urlsplit(self.base_url)
        job_info_url = "{}://{}/scheduler/job/{{}}".format(
            url.scheme, url.netloc
        )
        logging.debug("Job info LAVA url: {}".format(job_info_url))
        return job_info_url


def key_value_data(string):
    """Validate the string to be in the form key=value."""
    if string:
        key, value = string.split("=")
        if not (key and value):
            msg = "{} not in 'key=value' format.".format(string)
            raise argparse.ArgumentTypeError(msg)
        return {key: value}
    return {}


class StoreDictKeyPair(argparse.Action):
    """Class for storing key/pair values in a dictionary."""

    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        """Initialise the class."""
        self._nargs = nargs
        super().__init__(option_strings, dest, nargs=nargs, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        """Store data into the namespace."""
        values_dict = {}
        for item in values:
            values_dict.update(item)
        setattr(namespace, self.dest, values_dict)


def _parse_arguments(cli_args):
    """Parse arguments."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--lava-server",
        help="LAVA server URL",
        dest="lava_server",
        required=True,
    )
    parser.add_argument(
        "--lava-username",
        help="LAVA username",
        dest="lava_username",
        required=True,
    )
    parser.add_argument(
        "--lava-token",
        help="LAVA token for API",
        dest="lava_token",
        required=True,
    )
    parser.add_argument(
        "--device-type",
        help="Device type in LAVA",
        dest="device_type",
        choices=valid_device_types,
        required=True,
    )
    parser.add_argument(
        "--image-url",
        help="Image to flash onto the device",
        dest="image_url",
        required=True,
    )
    parser.add_argument(
        "--template-names",
        help="List of the templates to submit for testing",
        dest="template_names",
        nargs="+",
        required=True,
    )
    parser.add_argument(
        "--mbl-branch",
        help="Branch of MBL repositories",
        dest="mbl_branch",
        required=True,
    )
    # Optional arguments
    parser.add_argument(
        "--pipeline-data",
        help="Custom data to pass into the LAVA pipeline\n(E.g.: "
        "key1=value1 key2=value2)",
        dest="pipeline_data",
        nargs="+",
        metavar="key=value",
        type=key_value_data,
        action=StoreDictKeyPair,
        default="",
    )
    parser.add_argument(
        "--mbl-revisions",
        help="Revisions (SHA1 or tag) of MBL repositories\n(E.g.: mbl-core="
        "39e05108fd70fc2c207e6673cbebb8b088d6b5f0 mbl-cli=mbl-os-0.6.0)",
        dest="mbl_revisions",
        nargs="+",
        metavar="key=value",
        type=key_value_data,
        action=StoreDictKeyPair,
        default="",
    )
    parser.add_argument("--build-tag", help="Build tag", dest="build_tag")
    parser.add_argument("--build-url", help="Build url", dest="build_url")
    parser.add_argument(
        "--template-path",
        help="Path to LAVA job templates",
        dest="template_path",
        default=default_template_base_path,
    )
    parser.add_argument(
        "--notify-user",
        help="Enable email notification to the user",
        action="store_true",
        dest="notify_user",
        default=False,
    )
    parser.add_argument(
        "--notify-emails",
        help="Enable email notification to custom emails",
        dest="notify_emails",
        nargs="+",
        default=[],
    )
    parser.add_argument(
        "--lava-callback-domain",
        help="Notification callback domain",
        dest="callback_domain",
        default="",
    )
    parser.add_argument(
        "--lava-callback-port",
        help="Notification callback port",
        dest="callback_port",
        default="",
    )
    parser.add_argument(
        "--treasure-database",
        help="Name of the treasure data database to store the results in.",
        dest="treasure_database",
        default="",
    )
    parser.add_argument(
        "--debug",
        help="Enable debug messages",
        action="store_true",
        dest="debug",
        default=False,
    )
    parser.add_argument(
        "--dry-run",
        help="Prepare and write templates to tmp/.\n"
        "Don't submit to actual servers.",
        action="store_true",
        dest="dry_run",
    )
    parser.add_argument(
        "--poll-result",
        help="Poll for the lava result",
        action="store_true",
        dest="poll_result",
        default=False,
    )
    parser.add_argument(
        "--poll-interval",
        help="Poll interval for the lava queries",
        type=int,
        dest="poll_interval",
        default=600,
    )
    parser.add_argument(
        "--poll-retries",
        help="Maximum amount of times the result is polled",
        type=int,
        dest="poll_retries",
        default=5,
    )

    return parser.parse_args(cli_args)


def _set_default_args(args):
    """Set default arguments."""
    # Set default build tag name based on lava username
    default_build_tag = "{} build".format(args.lava_username)
    args.build_tag = args.build_tag if args.build_tag else default_build_tag
    logging.debug("Using build_tag: {}".format(args.build_tag))

    # Set null build_url if it doesn't exist
    default_build_url = "-"
    args.build_url = args.build_url if args.build_url else default_build_url
    logging.debug("Using build_url: {}".format(args.build_url))

    # Set notify_user to the same user who has submitted the job
    if args.notify_user:
        args.notify_user = args.lava_username

    return args


def _enable_debug_logging(debug=False):
    """Enable/disable DEBUG logging."""
    logger = logging.getLogger()
    if debug:
        logging_level = logging.DEBUG
    else:
        logging_level = logging.INFO
    logger.setLevel(logging_level)


def poll_result(poll_retries, poll_interval, job_ids, lava_server):
    """Poll result of the given job ids."""
    i = 0
    error_occurred = False
    while i < poll_retries:
        time.sleep(poll_interval)
        logging.debug("Polling for test results")
        for job_id in job_ids:
            status = lava_server.check_job_status(job_id)
            if status != JobStatusCode.NOT_FINISHED.value:
                job_ids.remove(job_id)
                if status != JobStatusCode.SUCCESS.value:
                    logging.error("Job %s failed", job_id)
                    error_occurred = True
                else:
                    logging.info("Job %s succeeded", job_id)
        if len(job_ids) == 0 and error_occurred is False:
            logging.debug("Finished polling jobs, all succeeded")
            return ExitCode.SUCCESS.value
        elif len(job_ids) == 0 and error_occurred is True:
            logging.debug("Finished polling jobs, failures detected")
            return ExitCode.SUCCESS.value
        i += 1
    logging.debug("Finished polling jobs, max retries reached")
    return ExitCode.ERROR.value


def _main(args):
    """Perform the main execution of the application."""
    try:
        # Get all the arguments
        args = _parse_arguments(args)

        # Set the logging level
        _enable_debug_logging(args.debug)

        # Set default args
        args = _set_default_args(args)

        # Check for black listing
        for image, devices in black_list_images.items():
            if image in args.image_url and args.device_type in devices:
                logging.error(
                    "Job black listed ({} not supported on {})".format(
                        image, args.device_type
                    )
                )
                return ExitCode.ERROR.value

        # Load LAVA templates
        lava_template = LAVATemplates(
            args.template_path, args.template_names, args.dry_run
        )

        # Create LAVA jobs yaml file from templates
        lava_jobs = lava_template.process(
            args.image_url,
            args.build_tag,
            args.build_url,
            args.mbl_branch,
            args.mbl_revisions,
            args.pipeline_data,
            args.notify_user,
            args.notify_emails,
            args.device_type,
            args.callback_domain,
            args.callback_port,
            args.treasure_database,
        )

        # Instantiate a LAVA server
        lava_server = LAVAServer(
            args.lava_server, args.lava_username, args.lava_token, args.dry_run
        )

        job_ids = []
        for lava_job in lava_jobs:
            # Submit the job to LAVA
            submitted_job_ids = lava_server.submit_job(lava_job)
            # Get the IDs and print the job info urls
            job_id_urls = lava_server.get_job_urls(submitted_job_ids)
            for job_id_url in job_id_urls:
                logging.info("Job submitted: {}".format(job_id_url))
            job_ids.extend(submitted_job_ids)

        if args.poll_result:
            return poll_result(
                args.poll_retries, args.poll_interval, job_ids, lava_server
            )

    except KeyboardInterrupt:
        logging.error("Ctrl-C detected. Stopping.")
        return ExitCode.CTRLC.value
    except Exception as e:
        logging.error(e)
        if args.debug:
            import traceback

            traceback.print_exc()
        return ExitCode.ERROR.value
    return ExitCode.SUCCESS.value


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
