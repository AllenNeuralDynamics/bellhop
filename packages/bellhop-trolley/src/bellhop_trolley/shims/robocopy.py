"""
Robocopy wrapper with human-readable keyword arguments.
"""

import logging
import subprocess
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class RobocopyOptions(BaseModel):
    """Pydantic model for robocopy options with command-line flag mappings."""

    # Copy options
    subdirectories: bool = Field(
        default=False, description="Copy subdirectories (but not empty ones)", serialization_alias="/S"
    )
    subdirectories_including_empty: bool = Field(
        default=False, description="Copy subdirectories including empty ones", serialization_alias="/E"
    )
    levels: int | None = Field(
        default=None, description="Only copy the top n levels of the source directory tree", serialization_alias="/LEV"
    )
    restart_mode: bool = Field(default=False, description="Copy files in restartable mode", serialization_alias="/Z")
    backup_mode: bool = Field(default=False, description="Copy files in Backup mode", serialization_alias="/B")
    restart_and_backup_mode: bool = Field(
        default=False, description="Use restartable mode; if access denied use Backup mode", serialization_alias="/ZB"
    )
    unbuffered_io: bool = Field(
        default=False, description="Copy using unbuffered I/O (recommended for large files)", serialization_alias="/J"
    )
    efsraw_mode: bool = Field(
        default=False, description="Copy all encrypted files in EFS RAW mode", serialization_alias="/EFSRAW"
    )

    # What to copy
    copy_all_file_info: bool = Field(
        default=False, description="Copy ALL file info (equivalent to /COPYALL)", serialization_alias="/COPYALL"
    )
    copy_data_attributes_timestamps: bool = Field(
        default=False, description="Copy Data, Attributes and Timestamps", serialization_alias="/COPY:DAT"
    )
    copy_data_attributes: bool = Field(
        default=False, description="Copy Data and Attributes", serialization_alias="/COPY:DA"
    )
    copy_data_only: bool = Field(default=False, description="Copy Data only", serialization_alias="/COPY:D")
    copy_attributes_only: bool = Field(default=False, description="Copy Attributes only", serialization_alias="/COPY:A")
    copy_timestamps_only: bool = Field(default=False, description="Copy Timestamps only", serialization_alias="/COPY:T")
    copy_security: bool = Field(default=False, description="Copy Security", serialization_alias="/COPY:S")
    copy_ownership: bool = Field(default=False, description="Copy Owner info", serialization_alias="/COPY:O")
    copy_audit: bool = Field(default=False, description="Copy Auditing info", serialization_alias="/COPY:U")
    copy_all: bool = Field(default=False, description="Copy ALL file info", serialization_alias="/COPY:ALL")
    no_copy_info: bool = Field(
        default=False, description="Copy NO file info (useful with /PURGE)", serialization_alias="/NOCOPY"
    )
    fix_security: bool = Field(
        default=False, description="Fix file Security on all files, even skipped files", serialization_alias="/SECFIX"
    )
    fix_times: bool = Field(
        default=False, description="Fix file Times on all files, even skipped files", serialization_alias="/TIMFIX"
    )

    # How to copy
    purge_destination: bool = Field(
        default=False, description="Delete dest files/dirs that no longer exist in source", serialization_alias="/PURGE"
    )
    mirror: bool = Field(
        default=False, description="Mirror a directory tree (equivalent to /E plus /PURGE)", serialization_alias="/MIR"
    )
    move_files: bool = Field(
        default=False, description="Move files (delete from source after copying)", serialization_alias="/MOV"
    )
    move_files_and_dirs: bool = Field(
        default=False, description="Move files AND dirs (delete from source after copying)", serialization_alias="/MOVE"
    )

    # File selection attributes
    include_attributes: str | None = Field(
        default=None, description="Only copy files with these attributes set", serialization_alias="/IA"
    )
    exclude_attributes: str | None = Field(
        default=None, description="Exclude files with these attributes set", serialization_alias="/XA"
    )
    exclude_changed_files: bool = Field(default=False, description="Exclude Changed files", serialization_alias="/XC")
    exclude_newer_files: bool = Field(default=False, description="Exclude Newer files", serialization_alias="/XN")
    exclude_older_files: bool = Field(default=False, description="Exclude Older files", serialization_alias="/XO")
    exclude_extra_files_dirs: bool = Field(
        default=False, description="Exclude Extra files and directories", serialization_alias="/XX"
    )
    exclude_lonely_files_dirs: bool = Field(
        default=False, description="Exclude Lonely files and directories", serialization_alias="/XL"
    )
    include_same_files: bool = Field(default=False, description="Include Same files", serialization_alias="/IS")
    include_tweaked_files: bool = Field(default=False, description="Include Tweaked files", serialization_alias="/IT")

    # File size selection
    maximum_file_size: int | None = Field(
        default=None, description="Maximum file size in bytes", serialization_alias="/MAX"
    )
    minimum_file_size: int | None = Field(
        default=None, description="Minimum file size in bytes", serialization_alias="/MIN"
    )
    maximum_file_age_days: int | None = Field(
        default=None, description="Maximum file age - exclude files older than n days", serialization_alias="/MAXAGE"
    )
    minimum_file_age_days: int | None = Field(
        default=None, description="Minimum file age - exclude files newer than n days", serialization_alias="/MINAGE"
    )
    maximum_last_access_days: int | None = Field(
        default=None,
        description="Maximum Last Access Date - exclude files unused since n",
        serialization_alias="/MAXLAD",
    )
    minimum_last_access_days: int | None = Field(
        default=None, description="Minimum Last Access Date - exclude files used since n", serialization_alias="/MINLAD"
    )

    # File and directory exclusion
    exclude_files: list[str] | None = Field(
        default=None, description="List of file names/patterns to exclude", serialization_alias="/XF"
    )
    exclude_directories: list[str] | None = Field(
        default=None, description="List of directory names to exclude", serialization_alias="/XD"
    )

    # Retry options
    retry_count: int = Field(
        default=1000000, description="Number of retries on failed copies", serialization_alias="/R"
    )
    retry_wait_seconds: int = Field(
        default=30, description="Wait time between retries in seconds", serialization_alias="/W"
    )

    # Logging options
    log_file: str | Path | None = Field(
        default=None, description="Output status to LOG file", serialization_alias="/LOG"
    )
    append_to_log: bool = Field(
        default=False, description="Append to log file instead of overwriting", serialization_alias="/LOG+"
    )
    verbose: bool = Field(
        default=False, description="Produce Verbose output, showing skipped files", serialization_alias="/V"
    )
    timestamp_output: bool = Field(
        default=False, description="Include source file Time Stamps in the output", serialization_alias="/TS"
    )
    no_file_sizes: bool = Field(default=False, description="Don't log file sizes", serialization_alias="/NFS")
    no_directory_list: bool = Field(
        default=False, description="No Directory List - don't log directory names", serialization_alias="/NDL"
    )
    no_file_list: bool = Field(
        default=False, description="No File List - don't log file names", serialization_alias="/NFL"
    )
    no_progress: bool = Field(
        default=False, description="No Progress - don't display percentage copied", serialization_alias="/NP"
    )
    estimate_time: bool = Field(
        default=False, description="Show Estimated Time of Arrival of copied files", serialization_alias="/ETA"
    )

    # Performance options
    multithread: int | None = Field(
        default=None, description="Do multi-threaded copies with n threads", serialization_alias="/MT"
    )

    # Job options
    job_name: str | None = Field(
        default=None, description="Take parameters from the named job file", serialization_alias="/JOB"
    )
    save_job: str | Path | None = Field(
        default=None, description="Save parameters to the named job file", serialization_alias="/SAVE"
    )
    quit_after_processing: bool = Field(
        default=False, description="Quit after processing command line", serialization_alias="/QUIT"
    )
    no_source_directory_check: bool = Field(
        default=False, description="No Source Directory check", serialization_alias="/NOSD"
    )
    no_destination_directory_check: bool = Field(
        default=False, description="No Destination Directory check", serialization_alias="/NODD"
    )

    # Windows-specific options
    compress_network_transfer: bool = Field(
        default=False, description="Request network compression during file transfer", serialization_alias="/COMPRESS"
    )
    use_fat_file_times: bool = Field(
        default=False, description="Use FAT File Times (2-second precision)", serialization_alias="/FFT"
    )
    assume_fat_file_times: bool = Field(
        default=False, description="Assume FAT File Times (2-second precision)", serialization_alias="/DST"
    )
    compensate_dst: bool = Field(
        default=False, description="Compensate for one-hour DST time differences", serialization_alias="/DST"
    )

    # Additional options
    create_directory_tree: bool = Field(
        default=False, description="Create directory tree structure only", serialization_alias="/CREATE"
    )
    list_only: bool = Field(
        default=False, description="List only - don't copy, timestamp or delete any files", serialization_alias="/L"
    )
    dry_run: bool = Field(
        default=False, description="Same as list_only - preview what would be copied", serialization_alias="/L"
    )

    # Security and permissions
    copy_ntfs_acls: bool = Field(default=False, description="Copy NTFS ACLs", serialization_alias="/SEC")
    no_inherit: bool = Field(default=False, description="Don't copy inheritable ACLs", serialization_alias="/NOOFFLOAD")
    enable_backup_privilege: bool = Field(
        default=False, description="Enable backup privilege", serialization_alias="/B"
    )
    enable_restore_privilege: bool = Field(
        default=False, description="Enable restore privilege", serialization_alias="/B"
    )

    def to_args(self) -> list[str]:
        """
        Convert the model to robocopy command-line arguments.

        Returns:
            List of command-line arguments for robocopy
        """
        args = []

        # Handle copy flags specially since multiple options map to /COPY:X
        copy_flags = []
        if self.copy_data_only or self.copy_data_attributes or self.copy_data_attributes_timestamps:
            copy_flags.append("D")
        if self.copy_attributes_only or self.copy_data_attributes or self.copy_data_attributes_timestamps:
            copy_flags.append("A")
        if self.copy_timestamps_only or self.copy_data_attributes_timestamps:
            copy_flags.append("T")
        if self.copy_security:
            copy_flags.append("S")
        if self.copy_ownership:
            copy_flags.append("O")
        if self.copy_audit:
            copy_flags.append("U")

        # Handle special cases
        special_fields = {
            "copy_data_only",
            "copy_attributes_only",
            "copy_timestamps_only",
            "copy_data_attributes",
            "copy_data_attributes_timestamps",
            "copy_security",
            "copy_ownership",
            "copy_audit",
            "log_file",
            "append_to_log",
            "dry_run",
        }

        for field_name, field_info in RobocopyOptions.model_fields.items():
            if field_name in special_fields:
                continue

            value = getattr(self, field_name)
            alias = field_info.serialization_alias

            # Skip None, False, and default values for retry options
            if value is None or value is False:
                continue
            if field_name == "retry_count" and value == 1000000:
                continue
            if field_name == "retry_wait_seconds" and value == 30:
                continue

            # Handle different value types
            if isinstance(value, bool) and value:
                # Mirror takes precedence over purge
                if field_name == "purge_destination" and self.mirror:
                    continue
                args.append(alias)
            elif isinstance(value, int) or isinstance(value, str) or isinstance(value, Path):
                args.append(f"{alias}:{value}")
            elif isinstance(value, list):
                args.append(alias)
                args.extend(value)

        # Add copy flags if any were set
        if copy_flags and not self.copy_all_file_info and not self.copy_all:
            args.append(f"/COPY:{''.join(copy_flags)}")

        # Handle log file with append flag
        if self.log_file:
            if self.append_to_log:
                args.append(f"/LOG+:{self.log_file}")
            else:
                args.append(f"/LOG:{self.log_file}")

        # Handle dry_run (same as list_only)
        if self.dry_run and not self.list_only:
            args.append("/L")

        return args


def robocopy(
    source: str | Path,
    destination: str | Path,
    files: str = "*.*",
    **options: RobocopyOptions,
) -> subprocess.CompletedProcess:
    """
    Execute robocopy with human-readable keyword arguments.

    Args:
        source: Source directory path
        destination: Destination directory path
        files: File pattern to copy (default: "*.*")
        **options: Keyword arguments matching RobocopyOptions field names

    Returns:
        subprocess.CompletedProcess: The completed process result

    Raises:
        FileNotFoundError: If robocopy is not found
        subprocess.CalledProcessError: If robocopy fails with non-recoverable error

    Example:
        # Basic copy with subdirectories
        result = robocopy(
            source="C:\\source",
            destination="D:\\backup",
            subdirectories=True,
            verbose=True
        )

        # Mirror directories (exact copy, removing extra files)
        result = robocopy(
            source="C:\\important_data",
            destination="D:\\mirror_backup",
            mirror=True,
            log_file="mirror_log.txt",
            verbose=True
        )

        # Copy only newer files with retry logic
        result = robocopy(
            source="C:\\working_files",
            destination="\\\\server\\backup",
            subdirectories=True,
            exclude_older_files=True,
            retry_count=5,
            retry_wait_seconds=10
        )
    """
    # Create RobocopyOptions instance from keyword arguments
    robo_options = RobocopyOptions(**options)

    # Build the robocopy command
    cmd = ["robocopy", str(source), str(destination), files]
    cmd.extend(robo_options.to_args())

    # Log the command being executed
    logger.info(f"Executing robocopy command: {' '.join(cmd)}")

    try:
        # Execute the command
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,  # Don't raise exception on non-zero exit codes
        )

        # Robocopy has special exit codes:
        # 0 = No files were copied. No failure was encountered. No files were mismatched.
        # 1 = All files were copied successfully.
        # 2 = There are some additional files in the destination directory that are not present in the source directory.
        # 3 = Some files were copied. Additional files were present.
        # 5 = Some files were copied. Some files were mismatched. No failure was encountered.
        # 6 = Additional files and mismatched files exist.
        # 7 = Files were copied, a file mismatch was present, and additional files were present.
        # 8 and above = There was at least one failure during the copy operation.

        if result.returncode >= 8:
            logger.error(f"Robocopy failed with exit code {result.returncode}")
            logger.error(f"STDOUT: {result.stdout}")
            logger.error(f"STDERR: {result.stderr}")
            raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
        elif result.returncode > 0:
            logger.info(f"Robocopy completed with exit code {result.returncode} (success with notes)")
        else:
            logger.info("Robocopy completed successfully")

        if robo_options.verbose or logger.isEnabledFor(logging.DEBUG):
            logger.info(f"STDOUT: {result.stdout}")
            if result.stderr:
                logger.warning(f"STDERR: {result.stderr}")

        return result

    except FileNotFoundError:
        logger.error("Robocopy command not found. Make sure you're running on Windows with robocopy available.")
        raise
    except Exception as e:
        logger.error(f"Error executing robocopy: {e}")
        raise


# Convenience functions for common use cases
def mirror_directories(
    source: str | Path,
    destination: str | Path,
    log_file: str | Path | None = None,
    verbose: bool = True,
    **kwargs,
) -> subprocess.CompletedProcess:
    """
    Mirror source directory to destination (exact copy, removing extra files).

    Args:
        source: Source directory
        destination: Destination directory
        log_file: Optional log file path
        verbose: Enable verbose output
        **kwargs: Additional arguments to pass to robocopy()

    Returns:
        subprocess.CompletedProcess: The completed process result
    """
    return robocopy(source=source, destination=destination, mirror=True, log_file=log_file, verbose=verbose, **kwargs)


def sync_directories(
    source: str | Path,
    destination: str | Path,
    exclude_older: bool = True,
    log_file: str | Path | None = None,
    verbose: bool = True,
    **kwargs,
) -> subprocess.CompletedProcess:
    """
    Sync directories, copying only newer files by default.

    Args:
        source: Source directory
        destination: Destination directory
        exclude_older: Skip files that are older than destination files
        log_file: Optional log file path
        verbose: Enable verbose output
        **kwargs: Additional arguments to pass to robocopy()

    Returns:
        subprocess.CompletedProcess: The completed process result
    """
    return robocopy(
        source=source,
        destination=destination,
        subdirectories=True,
        exclude_older_files=exclude_older,
        log_file=log_file,
        verbose=verbose,
        **kwargs,
    )


def backup_with_retry(
    source: str | Path,
    destination: str | Path,
    retry_count: int = 5,
    retry_wait_seconds: int = 30,
    log_file: str | Path | None = None,
    **kwargs,
) -> subprocess.CompletedProcess:
    """
    Backup directories with retry logic for network reliability.

    Args:
        source: Source directory
        destination: Destination directory
        retry_count: Number of retries on failures
        retry_wait_seconds: Wait time between retries
        log_file: Optional log file path
        **kwargs: Additional arguments to pass to robocopy()

    Returns:
        subprocess.CompletedProcess: The completed process result
    """
    return robocopy(
        source=source,
        destination=destination,
        subdirectories=True,
        restart_and_backup_mode=True,
        retry_count=retry_count,
        retry_wait_seconds=retry_wait_seconds,
        log_file=log_file,
        verbose=True,
        **kwargs,
    )
