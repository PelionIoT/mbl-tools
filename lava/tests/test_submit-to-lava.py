# Copyright (c) 2018, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Pytest tests.

Pytest is the framework used to run tests. It autodiscovers tests by the name
of the class or method/function. More info about autodiscovery:
https://docs.pytest.org/en/latest/goodpractices.html#test-discovery

Pytest documentation can be found here: https://docs.pytest.org/en/latest/

The aim of this file is to provide a basic unit test coverage for every class
and method in submit-to-lava.py file.

The structure follows the same structure of the module it is testing.
Every test is prefixed with "test_" followed by the name of the method under
test.

The generic structure of every test is:
    * Set up Mock objects
    * Call the method under test
    * Check the results

Sometime there is no need to set up mock objects hence it is skipped.

In order to check the results, python assert and mock asserts are used.
Every test has a docstring which explains what the test is testing/expecting.
"""

from unittest.mock import MagicMock, call
import xmlrpc.client


# The main file needs to be loaded and executed. "import" wouldn't work because
# the parent directory is not in the sys.path and it is not a module.
exec(open("./submit-to-lava.py").read())


class TestLAVATemplates(object):
    """Test methods in LAVATemplates class."""

    # Define common parameter which are used for every test
    lava_template_names = ["lava_template_name"]
    template_path = "/template/path"
    device_type = "imx7s-warp-mbl"
    dry_run = True

    def test___init__(self):
        """Test __init__() method.

        Check if the arguments passed are really set in the instance.
        """
        # Call the method under test
        lt = LAVATemplates(
            self.template_path, self.lava_template_names, self.dry_run
        )

        # Check the results
        assert lt.lava_template_names == self.lava_template_names
        assert lt.template_path == self.template_path
        assert lt.dry_run == self.dry_run

    def test_process(self):
        """Test process() method.

        The test check the following:
        * if _load_template is called with the name of the template to load
        * if the template is rendered with the right parameters
        * if _dump_job is called with job content and the template name
        * if process() returns a list of string (lava job).

        The test though doesn't check if the template is valid or not.
        """
        # Set up Mock objects
        lt = LAVATemplates(
            self.template_path, self.lava_template_names, self.dry_run
        )
        template_mock = MagicMock()
        template_mock.render.return_value = "some yaml string"
        lt._load_template = MagicMock(return_value=template_mock)
        lt._dump_job = MagicMock()

        # Call the method under test
        lava_jobs = lt.process(
            "img_url",
            "build_tag",
            "build_url",
            "mbl_branch",
            {"mbl-core": "12345"},
            "notify_user",
            ["notify_emails"],
            "imx7s-warp-mbl",
            "callback.domain",
            "callback.port",
        )

        # Check the results
        lt._load_template.assert_called_with("lava_template_name")
        template_mock.render.assert_called_with(
            build_tag="build_tag",
            build_url="build_url",
            mbl_branch="mbl_branch",
            mbl_revisions={"mbl-core": "12345"},
            image_url="img_url",
            notify_user="notify_user",
            notify_emails=["notify_emails"],
            device_type="imx7s-warp-mbl",
            callback_domain="callback.domain",
            callback_port="callback.port",
        )
        lt._dump_job.assert_called_with(
            "some yaml string", "imx7s-warp-mbl", "lava_template_name"
        )
        assert lava_jobs == ["some yaml string"]

    def test__dump_job(self, monkeypatch):
        """Test _dump_job() method.

        Check if the method writes the content to the path both specified as
        arguments. This is done mocking builtin.open method.
        """
        # Set up Mock objects
        lt = LAVATemplates(
            self.template_path, self.lava_template_names, self.dry_run
        )
        job_content = "job content"
        device_type = "imx7s-warp-mbl"
        template_name = "template.yaml"

        mock_open = MagicMock()
        monkeypatch.setattr("builtins.open", mock_open)

        # Call the method under test
        lt._dump_job(job_content, device_type, template_name)

        # Check the results
        expected_full_path = "tmp/imx7s-warp-mbl/template.yaml"
        calls = [
            call(expected_full_path, "w"),
            call().__enter__().write(job_content),
        ]
        mock_open.assert_has_calls(calls, any_order=True)

    def test__load_template(self, monkeypatch):
        """Test _load_template().

        Check if the jinja2 methods are called with the correct arguments.
        Jinja2 objects are all mocked.
        """
        # Set up Mock objects
        lt = LAVATemplates(
            self.template_path, self.lava_template_names, self.dry_run
        )

        mock_template_loader = MagicMock()
        mock_jinja2_fs_loader = MagicMock(return_value=mock_template_loader)
        mock_jinja2_env = MagicMock()
        monkeypatch.setattr("jinja2.FileSystemLoader", mock_jinja2_fs_loader)
        monkeypatch.setattr("jinja2.Environment", mock_jinja2_env)

        # Call the method under test
        lt._load_template("template name")

        # Check the results
        mock_jinja2_fs_loader.assert_called_once_with(
            searchpath=["/template/path/testplans", "/template/path"]
        )
        mock_jinja2_env.assert_has_calls(
            [
                call(
                    loader=mock_template_loader,
                    lstrip_blocks=True,
                    trim_blocks=True,
                ),
                call().get_template("template name"),
            ]
        )


class TestLAVAServer(object):
    """Test methods in LAVAServer class."""

    # Define common parameter which are used for every test
    server_url = "http://lava.server.url"
    username = "username"
    token = "token"
    dry_run = False

    def test___init__(self):
        """Test __init__() method.

        Check if the method setup the correct values based on the arguments
        passed. In fact based on server_url, username and token, the method
        calls other instance methods to set base_url, api_url and job_info_url.
        The connection should be xmlrpc ServerProxy instance.
        """
        # Call the method under test
        ls = LAVAServer(
            self.server_url, self.username, self.token, self.dry_run
        )

        # Check the results
        assert ls.base_url == "http://lava.server.url"
        assert ls.api_url == "http://username:token@lava.server.url/RPC2"
        assert ls.job_info_url == "http://lava.server.url/scheduler/job/{}"
        assert isinstance(ls.connection, xmlrpc.client.ServerProxy)
        assert ls.dry_run is False

    def test_submit_job(self):
        """Test submit_job() method.

        Check if the xmlrpc scheduler submit_job method is called with the
        expected data and if it returns a list of job IDs.
        """
        # Set up Mock objects
        ls = LAVAServer(
            self.server_url, self.username, self.token, self.dry_run
        )
        ls.connection = MagicMock()
        ls.connection.scheduler.submit_job.return_value = 5

        # Call the method under test
        job_ids = ls.submit_job("job definition")

        # Check the results
        assert job_ids == [5]
        ls.connection.scheduler.submit_job.assert_called_once_with(
            "job definition"
        )

    def test_get_job_urls(self):
        """Test _get_job_urls() method.

        Given a list of job IDs, check if the method returns the urls correctly
        formatted. In this case there is nothing to mock.
        """
        # Set up Mock objects
        ls = LAVAServer(
            self.server_url, self.username, self.token, self.dry_run
        )

        # Call the method under test
        job_urls = ls.get_job_urls([2, 3])

        # Check the results
        assert job_urls == [
            "http://lava.server.url/scheduler/job/2",
            "http://lava.server.url/scheduler/job/3",
        ]

    def test__connect(self):
        """Test _connect() method.

        Check if the method returns an instance of ServerProxy.
        """
        # Set up Mock objects
        ls = LAVAServer(
            self.server_url, self.username, self.token, self.dry_run
        )

        # Call the method under test
        connection = ls._connect()

        # Check the results
        assert isinstance(connection, xmlrpc.client.ServerProxy)

    def test__normalise_url(self):
        """Test _normalise() method.

        Check if the method behaves correctly depending on the input. If no
        scheme is passed, an https:// is added. If a scheme is passed, it keeps
        the same scheme.
        NOTE: this test is checking three different behaviours of the same
        method.
        """
        # Set up Mock objects
        ls = LAVAServer(
            self.server_url, self.username, self.token, self.dry_run
        )

        # Call the method under test
        url_without_scheme = ls._normalise_url("url.without.http")
        url_with_http = ls._normalise_url("http://url.without.https")
        url_with_https = ls._normalise_url("https://url.with.https")

        # Check the results
        assert url_without_scheme == "https://url.without.http"
        assert url_with_http == "http://url.without.https"
        assert url_with_https == "https://url.with.https"

    def test__get_api_url(self):
        """Test _get_api_url() method.

        Check if the method returns the correct LAVA API url.
        """
        # Set up Mock objects
        ls = LAVAServer(
            self.server_url, self.username, self.token, self.dry_run
        )

        # Call the method under test
        api_url = ls._get_api_url(self.username, self.token)

        # Check the results
        assert api_url == "http://username:token@lava.server.url/RPC2"

    def test__get_job_info_url(self):
        """Test _het_job_info_url() method.

        Check if the method returns the correct url for checking job info. The
        url ends with {} because it will be formatted with a job ID.
        """
        # Set up Mock objects
        ls = LAVAServer(
            self.server_url, self.username, self.token, self.dry_run
        )

        # Call the method under test
        job_info_url = ls._get_job_info_url()

        # Check the results
        assert job_info_url == "http://lava.server.url/scheduler/job/{}"


class TestParseArguments(object):
    """Test methods for dealing with arguments."""

    def test__parse_arguments(self):
        """Test _parse_arguments() function.

        Check if the arguments parser sets the correct values in the namespace.
        It checks if optional arguments are set to the correct default values.
        """
        # Set up Mock objects
        cli_args = []
        cli_args.extend(["--lava-server", "lava.server"])
        cli_args.extend(["--lava-username", "lava_username"])
        cli_args.extend(["--lava-token", "lava_token"])
        cli_args.extend(["--device-type", "imx7s-warp-mbl"])
        cli_args.extend(["--mbl-branch", "master"])
        cli_args.extend(["--mbl-revisions", "mbl-core:12345"])
        cli_args.extend(["--template-names", "helloworld-template.yaml"])
        cli_args.extend(["--image-url", "http://image.url/image.wic.gz"])

        # Call the method under test
        args = _parse_arguments(cli_args)

        # Check the results
        # Mandatory args
        assert args.lava_server == "lava.server"
        assert args.lava_username == "lava_username"
        assert args.lava_token == "lava_token"
        assert args.device_type == "imx7s-warp-mbl"
        assert args.mbl_branch == "master"
        assert args.template_names == ["helloworld-template.yaml"]
        assert args.image_url == "http://image.url/image.wic.gz"

        # Optional args
        assert args.mbl_revisions == {"mbl-core": "12345"}
        assert args.build_tag is None
        assert args.build_url is None
        assert args.template_path == "lava-job-definitions"
        assert args.notify_user is False
        assert args.notify_emails == []
        assert args.debug is False
        assert args.dry_run is False

    def test__set_default_args(self):
        """Test _set_default_args() method.

        Check if the method set the correct default arguments if the they are
        not set by the user.
        """
        # Set up Mock objects
        args = MagicMock()
        args.lava_username = "lava_username"
        args.build_tag = None
        args.build_url = None
        args.notify_user = True

        # Call the method under test
        args = _set_default_args(args)

        # Check the results
        assert args.build_tag == "lava_username build"
        assert args.build_url == "-"
        assert args.notify_user == "lava_username"


def test_repo_revision_list():
    """ Test repo_revision_list() function.

    This is used as type in argparse in order to convert a string with format
    "name1:sha1,name2:tag" into a dictionary"
    """
    revisions_argument = (
        "mbl-core:a7f9b77c16a3aa80daa4e378659226f628326a95,"
        "mbl-cli:mbl-os-0.6.1",
    )
    expected_result = {
        "mbl-core": "a7f9b77c16a3aa80daa4e378659226f628326a95",
        "mbl-cli": "mbl-os-0.6.1",
    }
    result = repo_revision_list(revisions_argument)
    assert result == expected_result


def test__enable_debug_logging(monkeypatch):
    """Test _enable_debug_logging() function.

    Check if the correct level of logging is set depending on debug argument.
    """
    # Call the method under test
    _enable_debug_logging(debug=True)

    # Check the results
    logger = logging.getLogger()
    assert logger.level == logging.DEBUG


def test__main(monkeypatch):
    """Test _main() function.

    Check if main executes core methods in order to have a correct behaviour.
    It mocks methods of both LAVATemplates and LAVAServer classes which are
    directly call in the main.
    """
    # Set up Mock objects
    cli_args = []
    cli_args.extend(["--lava-server", "lava.server"])
    cli_args.extend(["--lava-username", "lava_username"])
    cli_args.extend(["--lava-token", "lava_token"])
    cli_args.extend(["--device-type", "imx7s-warp-mbl"])
    cli_args.extend(["--mbl-branch", "master"])
    cli_args.extend(["--mbl-revisions", "mbl-core:12345"])
    cli_args.extend(["--template-names", "helloworld-template.yaml"])
    cli_args.extend(["--image-url", "http://image.url/image.wic.gz"])

    mock_process = MagicMock(return_value=["job1", "job2"])
    monkeypatch.setattr(LAVATemplates, "process", mock_process)

    mock_connect = MagicMock()
    monkeypatch.setattr(LAVAServer, "_connect", mock_connect)
    mock_submit_job = MagicMock()
    monkeypatch.setattr(LAVAServer, "submit_job", mock_submit_job)

    # Call the method under test
    _main(cli_args)

    # Check the results
    mock_process.assert_called_once_with(
        "http://image.url/image.wic.gz",
        "lava_username build",
        "-",
        "master",
        {"mbl-core": "12345"},
        False,
        [],
        "imx7s-warp-mbl",
    )
    mock_connect.assert_called_once_with()
    mock_submit_job.assert_has_calls(
        [call("job1"), call("job2")], any_order=True
    )
