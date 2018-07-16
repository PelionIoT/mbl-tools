from unittest.mock import MagicMock, call
import xmlrpc.client


# I need to load the main file
exec(open("./submit-to-lava.py").read())


class TestLAVATemplates(object):
    lava_template_names = ["lava_template_name"]
    template_path = "/template/path"
    device_type = "imx7s-warp"
    dry_run = True

    def test___init__(self):
        lt = LAVATemplates(self.template_path, self.device_type,
                           self.lava_template_names, self.dry_run)
        assert lt.lava_template_names == self.lava_template_names
        assert lt.template_path == self.template_path
        assert lt.device_type == self.device_type
        assert lt.dry_run == self.dry_run

    def test_process(self):
        # Set up Mock objects
        lt = LAVATemplates(self.template_path, self.device_type,
                           self.lava_template_names, self.dry_run)
        template_mock = MagicMock()
        template_mock.render.return_value = "some yaml string"
        lt._load_template = MagicMock(return_value=template_mock)
        lt._dump_job = MagicMock()

        # Call the method under test
        lava_jobs = lt.process("img_url", "build_tag", "build_url")

        # Check the results
        lt._load_template.assert_called_with('lava_template_name')
        template_mock.render.assert_called_with(build_tag='build_tag',
                                                build_url='build_url',
                                                image_url='img_url')
        lt._dump_job.assert_called_with("some yaml string",
                                        "lava_template_name")
        assert lava_jobs == ["some yaml string"]

    def test__dump_job(self, monkeypatch):
        # Set up Mock objects
        lt = LAVATemplates(self.template_path, self.device_type,
                           self.lava_template_names, self.dry_run)
        job_content = "job content"
        device_type = "imx7s-warp"
        template_name = "template.yaml"

        mock_open = MagicMock()
        monkeypatch.setattr("builtins.open", mock_open)
        # Call the method under test
        lt._dump_job(job_content, template_name)

        # Check the results
        expected_full_path = "tmp/imx7s-warp/template.yaml"
        calls = [call(expected_full_path, 'w'),
                 call().__enter__().write(job_content)]
        mock_open.assert_has_calls(calls, any_order=True)

    def test__load_template(self, monkeypatch):
        # Set up Mock objects
        lt = LAVATemplates(self.template_path, self.device_type,
                           self.lava_template_names, self.dry_run)

        mock_jinja2_fs_loader = MagicMock()
        mock_jinja2_env = MagicMock()
        monkeypatch.setattr("jinja2.FileSystemLoader", mock_jinja2_fs_loader)
        monkeypatch.setattr("jinja2.Environment", mock_jinja2_env)

        # Call the method under test
        lt._load_template("template name")

        # Check the results
        calls = [call(searchpath='/template/path/imx7s-warp'),
                 call().get_template('template name')]
        mock_jinja2_fs_loader.assert_called_once_with(
            searchpath='/template/path/imx7s-warp')
        mock_jinja2_env.assert_has_calls(
            [call().get_template('template name')],
            any_order=True)


class TestLAVAServer(object):
    server_url = "http://lava.server.url"
    username = "username"
    token = "token"
    dry_run = False

    def test___init__(self):
        # Call the method under test
        ls = LAVAServer(self.server_url, self.username, self.token,
                        self.dry_run)

        # Check the results
        assert ls.base_url == "http://lava.server.url"
        assert ls.api_url == "http://username:token@lava.server.url/RPC2"
        assert ls.job_info_url == "http://lava.server.url/scheduler/job/{}"
        assert isinstance(ls.connection, xmlrpc.client.ServerProxy)
        assert ls.dry_run is False

    def test_submit_job(self):
        # Set up Mock objects
        ls = LAVAServer(self.server_url, self.username, self.token,
                        self.dry_run)
        ls.connection = MagicMock()
        ls.connection.scheduler.submit_job.return_value = 5

        # Call the method under test
        job_ids = ls.submit_job("job definition")

        # Check the results
        assert job_ids == [5]
        ls.connection.scheduler.submit_job.assert_called_once_with(
            "job definition")

    def test_get_job_urls(self):
        # Set up Mock objects
        ls = LAVAServer(self.server_url, self.username, self.token,
                        self.dry_run)

        # Call the method under test
        job_urls = ls.get_job_urls([2, 3])

        # Check the results
        assert job_urls == ['http://lava.server.url/scheduler/job/2',
                            'http://lava.server.url/scheduler/job/3']

    def test__connect(self):
        # Set up Mock objects
        ls = LAVAServer(self.server_url, self.username, self.token,
                        self.dry_run)

        # Call the method under test
        connection = ls._connect()

        # Check the results
        assert isinstance(connection, xmlrpc.client.ServerProxy)

    def test__normalise_url(self):
        # Set up Mock objects
        ls = LAVAServer(self.server_url, self.username, self.token,
                        self.dry_run)

        # Call the method under test
        url_without_scheme = ls._normalise_url("url.without.http")
        url_with_http = ls._normalise_url("http://url.without.https")
        url_with_https = ls._normalise_url("https://url.with.https")

        # Check the results
        assert url_without_scheme == "https://url.without.http"
        assert url_with_http == "http://url.without.https"
        assert url_with_https == "https://url.with.https"

    def test__get_api_url(self):
        # Set up Mock objects
        ls = LAVAServer(self.server_url, self.username, self.token,
                        self.dry_run)

        # Call the method under test
        api_url = ls._get_api_url(self.username, self.token)

        # Check the results
        assert api_url == "http://username:token@lava.server.url/RPC2"

    def test__get_job_info_url(self):
        # Set up Mock objects
        ls = LAVAServer(self.server_url, self.username, self.token,
                        self.dry_run)

        # Call the method under test
        job_info_url = ls._get_job_info_url()

        # Check the results
        assert job_info_url == "http://lava.server.url/scheduler/job/{}"


class TestParseArguments(object):
    def test__parse_arguments(self):
        # Set up Mock objects
        # Call the method under test
        # Check the results
        assert True


def test__enable_debug_logging():
    # Set up Mock objects
    # Call the method under test
    # Check the results
    assert True


def test__main():
    # Set up Mock objects
    # Call the method under test
    # Check the results
    assert True