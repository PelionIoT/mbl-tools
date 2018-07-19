#!/usr/bin/env python3

# Copyright (c) 2017 ARM Ltd.
#
# SPDX-License-Identifier: Apache-2.0

import argparse
import logging
import sys
import os
import xmlrpc.client
import urllib

import jinja2


default_template_base_path = "lava-job-definitions"
default_template_name = "template.yaml"


class LAVATemplates(object):
    """LAVA templates class."""
    def __init__(self, template_path, device_type, lava_template_names,
                 dry_run):
        self.template_path = template_path
        self.device_type = device_type
        self.lava_template_names = lava_template_names
        self.dry_run = dry_run

    def process(self, image_url, build_tag, build_url, notify_user,
                notify_email):
        """Process templates rendering them with the right values."""
        lava_jobs = []
        for template_name in self.lava_template_names:
            template = self._load_template(template_name)
            lava_job = template.render(image_url=image_url,
                                       build_tag=build_tag,
                                       build_url=build_url,
                                       notify_user=notify_user,
                                       notify_email=notify_email)
            lava_jobs.append(lava_job)
            if self.dry_run:
                self._dump_job(lava_job, template_name)
        return lava_jobs

    def _dump_job(self, job, template_name):
        """Dump LAVA job into yaml files under tmp/ directory structure."""
        output_path = "tmp"
        testpath = os.path.join(output_path, self.device_type, template_name)
        logging.info("Dumping job data into {}".format(testpath))
        if not os.path.exists(os.path.dirname(testpath)):
            os.makedirs(os.path.dirname(testpath))
        with open(testpath, "w") as f:
            f.write(job)

    def _load_template(self, template_name):
        """Return a jinja2 template starting from a yaml file on disk."""
        try:
            if template_name:
                template_full_path = os.path.join(self.template_path,
                                                  self.device_type)
                template_loader = jinja2.FileSystemLoader(
                    searchpath=template_full_path)
                template_env = jinja2.Environment(loader=template_loader)
                template = template_env.get_template(template_name)
        except jinja2.exceptions.TemplateNotFound as e:
            raise Exception("Cannot find template {} on {}"
                            .format(template_name, template_full_path))
        return template


class LAVAServer(object):
    """LAVA server class."""

    def __init__(self, server_url, username, token, dry_run):
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
        if not (server_url.startswith("http://") or
                server_url.startswith("https://")):
            server_url = "https://{}".format(server_url)
        logging.debug("Base LAVA url: {}".format(server_url))
        return server_url

    def _get_api_url(self, username, token):
        """Return LAVA API url."""
        url = urllib.parse.urlsplit(self.base_url)
        api_url = "{}://{}:{}@{}/RPC2".format(url.scheme, username, token,
                                              url.netloc)
        logging.debug("API LAVA url: {}".format(api_url))
        return api_url

    def _get_job_info_url(self):
        """Return LAVA base url for job details."""
        url = urllib.parse.urlsplit(self.base_url)
        job_info_url = "{}://{}/scheduler/job/{{}}".format(url.scheme,
                                                           url.netloc)
        logging.debug("Job info LAVA url: {}".format(job_info_url))
        return job_info_url


def _parse_arguments(cli_args):
    """Arguments parser."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--lava-server",
                        help="LAVA server URL",
                        dest="lava_server",
                        required=True)
    parser.add_argument("--lava-username",
                        help="LAVA username",
                        dest="lava_username",
                        required=True)
    parser.add_argument("--lava-token",
                        help="LAVA token for API",
                        dest="lava_token",
                        required=True)
    parser.add_argument("--device-type",
                        help="Device type in LAVA",
                        dest="device_type",
                        required=True)
    parser.add_argument("--image-url",
                        help="Image to flash onto the device",
                        dest="image_url",
                        required=True)
    parser.add_argument("--build-tag",
                        help="Build tag",
                        dest="build_tag")
    parser.add_argument("--build-url",
                        help="Build url",
                        dest="build_url")
    parser.add_argument("--template-path",
                        help="Path to LAVA job templates",
                        dest="template_path",
                        default=default_template_base_path)
    parser.add_argument("--template-names",
                        help="list of the templates to submit for testing",
                        dest="template_names",
                        nargs="+",
                        default=[default_template_name])
    parser.add_argument("--notify-user",
                        help="Enable email notification to the user",
                        action="store_true",
                        dest="notify_user",
                        default=False)
    parser.add_argument("--notify-email",
                        help="Enable email notification to a custom email",
                        dest="notify_email",
                        default=None)
    parser.add_argument("--debug",
                        help="Enable debug messages",
                        action="store_true",
                        dest="debug",
                        default=False)
    parser.add_argument("--dry-run",
                        help="""Prepare and write templates to tmp/.
                        Don"t submit to actual servers.""",
                        action="store_true",
                        dest="dry_run")

    return parser.parse_args(cli_args)


def _set_default_args(args):
    """Set default arguments """
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
    """Main execution of the application."""
    try:
        # Get all the arguments
        args = _parse_arguments(args)

        # Set the logging level
        _enable_debug_logging(args.debug)

        # Set default args
        args = _set_default_args(args)

        # Load LAVA templates
        lava_template = LAVATemplates(args.template_path, args.device_type,
                                      args.template_names, args.dry_run)

        # Create LAVA jobs yaml file from templates
        lava_jobs = lava_template.process(args.image_url, args.build_tag,
                                          args.build_url, args.notify_user,
                                          args.notify_email)

        # Instantiate a LAVA server
        lava_server = LAVAServer(args.lava_server, args.lava_username,
                                 args.lava_token, args.dry_run)

        for lava_job in lava_jobs:
            # Submit the job to LAVA
            job_ids = lava_server.submit_job(lava_job)
            # Get the IDs and print the job info urls
            job_id_urls = lava_server.get_job_urls(job_ids)
            for job_id_url in job_id_urls:
                logging.info("Job submitted: {}".format(job_id_url))

    except KeyboardInterrupt:
        logging.error("Ctrl-C detected. Stopping.")
        return 1
    except Exception as e:
        import traceback
        logging.error(e)
        traceback.print_exc()
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
