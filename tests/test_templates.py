import pytest
from bellhop_models.specifications import JobSpecification

from bellhop.job_templates import Config, TemplateManager

SELF_TEST = "self_test_template"


@pytest.fixture
def sample_template():
    return """
key: value
key2: {{ value2 }}
key3: {{ value3 | default('default_value3') }}
"""


@pytest.fixture
def template_manager(tmp_path, sample_template) -> TemplateManager:
    config = Config(data_dir=tmp_path)
    manager = TemplateManager(config)
    template_file = config.job_templates_dir / "sample_template.yaml.j2"
    template_file.write_text(sample_template)
    return manager


def test_init_copies_self_test_template(template_manager: TemplateManager):
    assert SELF_TEST in template_manager.list_templates()


def test_list_templates_includes_sample(template_manager: TemplateManager):
    assert "sample_template" in template_manager.list_templates()


def test_read_template_returns_content(template_manager: TemplateManager, sample_template):
    assert template_manager.read_template("sample_template") == sample_template


def test_read_template_missing_raises(template_manager: TemplateManager):
    with pytest.raises(FileNotFoundError):
        template_manager.read_template("does_not_exist")


def test_get_template_variables_returns_list(template_manager: TemplateManager):
    assert template_manager.get_template_variables("sample_template") == ["value2", "value3"]


def test_get_template_defaults_returns_literal_defaults(template_manager: TemplateManager):
    assert template_manager.get_template_defaults("sample_template") == {"value3": "default_value3"}


def test_render_template_raw_substitutes_values(template_manager: TemplateManager):
    rendered = template_manager.render_template_raw("sample_template", {"value2": "V2", "value3": "V3"})
    assert "key2: V2" in rendered
    assert "key3: V3" in rendered


def test_render_template_to_jobspec_returns_jobspec(template_manager: TemplateManager):
    spec = template_manager.render_template_to_jobspec(
        SELF_TEST, {"name": "run-1", "tester_name": "alice", "delete_files": False}
    )
    assert isinstance(spec, JobSpecification)
    assert spec.name == "Bellhop self-test run-1"


def test_create_template_persists_file(template_manager: TemplateManager):
    template_manager.create_template("new_one", "name: n\ntasks: []\n")
    assert "new_one" in template_manager.list_templates()


def test_create_template_existing_raises(template_manager: TemplateManager):
    with pytest.raises(FileExistsError):
        template_manager.create_template("sample_template", "name: other\ntasks: []\n")


def test_update_template_changes_content(template_manager: TemplateManager):
    template_manager.update_template("sample_template", "name: after\ntasks: []\n")
    assert template_manager.read_template("sample_template") == "name: after\ntasks: []\n"


def test_update_template_missing_raises(template_manager: TemplateManager):
    with pytest.raises(FileNotFoundError):
        template_manager.update_template("nope", "name: n\ntasks: []\n")


def test_delete_template_removes_file(template_manager: TemplateManager):
    template_manager.delete_template("sample_template")
    assert "sample_template" not in template_manager.list_templates()


def test_delete_template_missing_raises(template_manager: TemplateManager):
    with pytest.raises(FileNotFoundError):
        template_manager.delete_template("nope")
