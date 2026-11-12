"""
Example usage of the robocopy module with Pydantic-based options.
"""

from bellhop_trolley.shims.robocopy import RobocopyOptions, robocopy


def basic_example():
    """Basic robocopy usage with keyword arguments."""
    result = robocopy(
        source="C:\\source",
        destination="D:\\backup",
        subdirectories=True,
        verbose=True,
        dry_run=True,  # Preview what would be copied
    )
    print(f"Exit code: {result.returncode}")


def advanced_example():
    """Advanced usage with RobocopyOptions model directly."""
    # Create options model with all the robocopy flags
    options = RobocopyOptions(
        subdirectories_including_empty=True,
        mirror=True,
        retry_count=5,
        retry_wait_seconds=10,
        log_file="backup.log",
        verbose=True,
        multithread=8,
        compress_network_transfer=True,
    )

    # Inspect the command that will be generated
    args = options.to_args()
    print(f"Robocopy arguments: {args}")
    # Output: ['/E', '/MIR', '/R:5', '/W:10', '/V', '/MT:8', '/COMPRESS', '/LOG:backup.log']

    # Each field has its description and serialization alias (the robocopy flag)
    for field_name, field_info in options.model_fields.items():
        value = getattr(options, field_name)
        if value not in (None, False, 1000000, 30):  # Skip defaults
            print(f"{field_name}: {field_info.description} -> {field_info.serialization_alias}")


def inspect_all_options():
    """Show all available options with their robocopy flags."""
    options = RobocopyOptions()

    print("\n=== All RobocopyOptions Fields ===\n")
    for field_name, field_info in options.model_fields.items():
        alias = field_info.serialization_alias
        desc = field_info.description
        default = field_info.default
        print(f"{field_name:40} -> {alias:15} | {desc}")


if __name__ == "__main__":
    print("=== Basic Example ===")
    # basic_example()  # Uncomment to run (requires Windows)

    print("\n=== Advanced Example ===")
    advanced_example()

    print("\n=== All Options ===")
    inspect_all_options()
