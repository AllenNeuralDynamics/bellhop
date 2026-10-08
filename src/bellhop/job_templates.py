from pathlib import Path

import yaml
from bellhop_models.specifications import JobSpecification
from jinja2 import Environment, FileSystemLoader, meta


# TODO: maybe move template stuff to bellhop-models
class TemplateManager:
    def __init__(self, template_dir: Path):
        self.template_dir = template_dir.resolve()
        self.jinja_env = Environment(loader=FileSystemLoader(self.template_dir))

    def list_templates(self) -> list[str]:
        return [p.stem for p in self.template_dir.glob("*.yaml.j2")]

    def read_template(self, name: str) -> str:
        path = self.template_dir / f"{name}.yaml.j2"
        if not path.exists():
            raise FileNotFoundError(f"Template '{name}.yaml.j2' does not exist.")
        return path.read_text()

    def get_template_variables(self, name: str) -> list[str]:
        template = self.jinja_env.get_template(f"{name}.yaml.j2")
        ast = self.jinja_env.parse(template.render())
        return list(meta.find_undeclared_variables(ast))

    def render_template_raw(self, name: str, values: dict) -> str:
        template = self.jinja_env.get_template(f"{name}.yaml.j2")
        return template.render(**values)

    def render_template_to_jobspec(self, name: str, values: dict) -> JobSpecification:
        return JobSpecification.model_validate(yaml.safe_load(self.render_template_raw(name, values)))

    def create_template(self, name: str, content: str) -> None:
        path = self.template_dir / f"{name}.yaml.j2"
        if path.exists():
            raise FileExistsError(f"Template '{name}.yaml.j2' already exists, use update_template to modify.")
        path.write_text(content)

    def update_template(self, name: str, content: str) -> None:
        path = self.template_dir / f"{name}.yaml.j2"
        if path.exists():
            path.write_text(content)
        else:
            raise FileNotFoundError(f"Template '{name}.yaml.j2' does not exist, use create_template to create it.")

    def delete_template(self, name: str) -> None:
        path = self.template_dir / f"{name}.yaml.j2"
        if path.exists():
            path.unlink()
        else:
            raise FileNotFoundError(f"Template '{name}.yaml.j2' does not exist.")