from unittest.mock import MagicMock, call


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
    def test___init__(self):
        assert False

    def test_submit_job(self):
        assert False

    def test_get_job_urls(self):
        assert False

    def test__connect(self):
        assert False

    def test__normalise_url(self):
        assert False

    def test__get_api_url(self):
        assert False

    def test__get_job_info_url(self):
        assert False


class TestParseArguments(object):
    def test__parse_arguments(self):
        assert False


def test__enable_debug_logging():
    assert False


def test__main():
    assert False
