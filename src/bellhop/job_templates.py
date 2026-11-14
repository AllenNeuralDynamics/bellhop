import importlib.resources
import os
import shutil
from pathlib import Path

import yaml
from bellhop_models.specifications import JobSpecification
from jinja2 import Environment, FileSystemLoader, meta, nodes

from bellhop.config import Config


def _make_dummy_data(folder: Path) -> None:
    files = [
        "file1.txt",
        "file2.txt",
        "dir1/file3.txt",
        "dir2/file4.txt",
        "dir2/subdir1/file5.txt",
    ]
    for name in files:
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(os.urandom(50 * 1_000))


# TODO: maybe move template stuff to bellhop-models
class TemplateManager:
    def __init__(self, config: Config, template_extension: str = ".yaml.j2"):
        self.template_dir = config.job_templates_dir.resolve()
        self.template_dir.mkdir(parents=True, exist_ok=True)
        self.template_extension = template_extension
        self._setup_self_test_template(config)
        self.jinja_env = Environment(loader=FileSystemLoader(self.template_dir))

    def _setup_self_test_template(self, config: Config) -> None:
        # This path needs to match the one in the template TODO: make that less brittle
        _make_dummy_data(config.data_dir / "self_test" / "dummy_data")
        self_test_template = (
            importlib.resources.files("bellhop.resources") / f"self_test_template{self.template_extension}"
        )
        shutil.copy(self_test_template, self.template_dir)

    def list_templates(self) -> list[str]:
        return [
            p.name.removesuffix(self.template_extension) for p in self.template_dir.glob(f"*{self.template_extension}")
        ]

    def read_template(self, name: str) -> str:
        path = self.template_dir / f"{name}{self.template_extension}"
        if not path.exists():
            raise FileNotFoundError(f"Template '{name}{self.template_extension}' does not exist.")
        return path.read_text()

    def get_template_variables(self, name: str) -> list[str]:
        # Parse the raw source; rendering first would substitute the variables away.
        ast = self.jinja_env.parse(self.read_template(name))
        return sorted(meta.find_undeclared_variables(ast))

    def get_template_defaults(self, name: str) -> dict[str, object]:
        # Pull literal defaults from ``var | default(...)`` filters; computed defaults are skipped.
        ast = self.jinja_env.parse(self.read_template(name))
        defaults: dict[str, object] = {}
        for node in ast.find_all(nodes.Filter):
            if node.name != "default" or not isinstance(node.node, nodes.Name):
                continue
            if node.args and isinstance(node.args[0], nodes.Const):
                defaults[node.node.name] = node.args[0].value
        return defaults

    def render_template_raw(self, name: str, values: dict) -> str:
        template = self.jinja_env.get_template(f"{name}{self.template_extension}")
        return template.render(**values)

    def render_template_to_jobspec(self, name: str, values: dict) -> JobSpecification:
        return JobSpecification.model_validate(yaml.safe_load(self.render_template_raw(name, values)))

    def create_template(self, name: str, content: str) -> None:
        path = self.template_dir / f"{name}{self.template_extension}"
        if path.exists():
            raise FileExistsError(
                f"Template '{name}{self.template_extension}' already exists, use update_template to modify."
            )
        path.write_text(content)

    def update_template(self, name: str, content: str) -> None:
        path = self.template_dir / f"{name}{self.template_extension}"
        if path.exists():
            path.write_text(content)
        else:
            raise FileNotFoundError(
                f"Template '{name}{self.template_extension}' does not exist, use create_template to create it."
            )

    def delete_template(self, name: str) -> None:
        path = self.template_dir / f"{name}{self.template_extension}"
        if path.exists():
            path.unlink()
        else:
            raise FileNotFoundError(f"Template '{name}{self.template_extension}' does not exist.")
