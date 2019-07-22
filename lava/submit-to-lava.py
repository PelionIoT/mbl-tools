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
import xmlrpc.client
import urllib

import jinja2


default_template_base_path = "lava-job-definitions"

valid_device_types = (
    "bcm2837-rpi-3-b-32",
    "bcm2837-rpi-3-b-plus-32",
    "imx7s-warp-mbl",
    "imx7d-pico-mbl",
    "imx8mmevk-mbl",
    "imx6ul-pico-mbl",
)


class ExitCode(enum.Enum):
    """Application return codes."""

    SUCCESS = 0
    CTRLC = 1
    ERROR = 2


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
        notify_user,
        notify_emails,
        device_type,
        callback_domain,
        callback_port,
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
                notify_user=notify_user,
                notify_emails=notify_emails,
                device_type=device_type,
                callback_domain=callback_domain,
                callback_port=callback_port,
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


def repo_revision_list(string):
    """Parse the string to create a dictionary of repos and revisions."""
    value = {}
    # The format shoudl be: repo1-name:sha1,repo2-name:tagname
    # There is no need to wrap it in a try-except block as argparse will take
    # care of it in case of Exception
    for data in string.split(","):
        repo_name, repo_revision = data.split(":")
        if not repo_revision:
            msg = "revision for {} is empty".format(repo_name)
            raise argparse.ArgumentTypeError(msg)
        value[repo_name] = repo_revision
    return value


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
        "--mbl-revisions",
        help="Revisions (SHA1 or tag) of MBL repositories\n(E.g.: mbl-core:"
        "39e05108fd70fc2c207e6673cbebb8b088d6b5f0,mbl-cli:mbl-os-0.6.0)",
        type=repo_revision_list,
        dest="mbl_revisions",
        default={},
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
        required=False,
    )
    parser.add_argument(
        "--lava-callback-port",
        help="Notification callback port",
        dest="callback_port",
        default="",
        required=False,
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


def _main(args):
    """Perform the main execution of the application."""
    try:
        # Get all the arguments
        args = _parse_arguments(args)

        # Set the logging level
        _enable_debug_logging(args.debug)

        # Set default args
        args = _set_default_args(args)

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
            args.notify_user,
            args.notify_emails,
            args.device_type,
            args.callback_domain,
            args.callback_port,
        )

        # Instantiate a LAVA server
        lava_server = LAVAServer(
            args.lava_server, args.lava_username, args.lava_token, args.dry_run
        )

        for lava_job in lava_jobs:
            # Submit the job to LAVA
            job_ids = lava_server.submit_job(lava_job)
            # Get the IDs and print the job info urls
            job_id_urls = lava_server.get_job_urls(job_ids)
            for job_id_url in job_id_urls:
                logging.info("Job submitted: {}".format(job_id_url))

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
