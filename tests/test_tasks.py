from typing import get_type_hints, get_args

from pydantic import BaseModel
import pytest

from bellhop_models.specifications import TaskTypes, AnyTask
from bellhop.task_executors import task_executor_registry


@pytest.mark.parametrize("task_type", get_args(TaskTypes))
def test_verify_executor_registry_task_types(task_type):
    """Verify that all TaskTypes have a corresponding executor in the registry."""
    assert task_type in task_executor_registry, f"Missing executor for task type: {task_type}"


def _union_annotation_to_dict(annotation) -> dict:
    """Convert a discriminated union annotation into a dictionary mapping literal tags to models."""
    # Extract the inner Union parts (Cat, Dog)
    union_type = get_args(annotation)[0]
    models = get_args(union_type)

    # Extract the discriminator field name (e.g., 'pet_type')
    discriminator_obj = get_args(annotation)[1]
    # In Pydantic v2, it can be a string or a Discriminator object
    if isinstance(discriminator_obj, str):
        discriminator_field = discriminator_obj
    else:
        discriminator_field = discriminator_obj.discriminator

    # Map the literal tags to the actual models
    mapping = {}
    for model in models:
        # Look up the Literal value assigned to the discriminator field
        tag_annotation = model.__annotations__[discriminator_field]
        tag_value = get_args(tag_annotation)[0]
        mapping[tag_value] = model

    return mapping


@pytest.mark.parametrize("task_type", get_args(TaskTypes))
def test_verify_executor_registry_params(task_type):
    """Verify that all TaskTypes have a corresponding executor in the registry."""
    executor = task_executor_registry[task_type]
    hints = get_type_hints(executor)

    task_lookup = _union_annotation_to_dict(AnyTask)
    task_model: type[BaseModel] = task_lookup[task_type]
    assert hints["params"] == task_model.model_fields["parameters"].annotation, (
        f"Executor for task type '{task_type}' has mismatched parameters. "
        f"Expected: {task_model.model_fields['parameters'].annotation}, "
        f"Found: {hints['params']}"
    )
