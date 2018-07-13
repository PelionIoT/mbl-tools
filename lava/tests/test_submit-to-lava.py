# I need to load the main file
exec(open("./submit-to-lava.py").read())

from unittest.mock import MagicMock

class TestLAVATemplates(object):
    lava_template_names = ["lava_template_name"]
    template_path = "/template/path"
    device_type = "imx7s-warp"
    dry_run = True

    def test___init__(self):
        lt = LAVATemplates(self.lava_template_names, self.template_path, self.device_type,
                           self.dry_run)
        assert lt.lava_template_names == self.lava_template_names
        assert lt.template_path == self.template_path
        assert lt.device_type == self.device_type
        assert lt.dry_run == self.dry_run

    def test_process(self):
        # Set up Mock objects
        lt = LAVATemplates(self.lava_template_names, self.template_path, self.device_type,
                           self.dry_run)
        template_mock = MagicMock()
        template_mock.render.return_value = "some yaml string"
        lt._load_template = MagicMock(return_value=template_mock)
        lt._dump_job = MagicMock()

        # Call the method under test
        lava_jobs = lt.process("img_url", "build_tag", "build_url")

        # Check the results
        lt._load_template.assert_called_with('lava_template_name',
                                             '/template/path',
                                             'imx7s-warp')
        template_mock.render.assert_called_with(build_tag='build_tag',
                                                build_url='build_url',
                                                image_url='img_url')
        lt._dump_job.assert_called_with("some yaml string", "imx7s-warp",
                                        "lava_template_name")
        assert lava_jobs == ["some yaml string"]

    def test__dump_job(self):
        assert False

    def test__load_template(self):
        assert False


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
