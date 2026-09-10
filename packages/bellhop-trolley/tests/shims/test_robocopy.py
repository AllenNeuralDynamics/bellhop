"""
Unit tests for the robocopy wrapper module.
"""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from bellhop_trolley.shims.robocopy import (
    RobocopyOptions,
    backup_with_retry,
    mirror_directories,
    robocopy,
    sync_directories,
)

# ── Helpers ──────────────────────────────────────────────────────────────────


def _completed(returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["robocopy"],
        returncode=returncode,
        stdout="mocked stdout",
        stderr="",
    )


# ── RobocopyOptions default / retry suppression ──────────────────────────────


class TestRobocopyOptionsDefaults:
    def test_all_defaults_produce_no_args(self):
        assert RobocopyOptions().to_args() == []

    def test_default_retry_count_suppressed(self):
        assert "/R:1000000" not in RobocopyOptions(retry_count=1000000).to_args()

    def test_default_retry_wait_suppressed(self):
        assert "/W:30" not in RobocopyOptions(retry_wait_seconds=30).to_args()

    def test_non_default_retry_count_included(self):
        assert "/R:5" in RobocopyOptions(retry_count=5).to_args()

    def test_non_default_retry_wait_included(self):
        assert "/W:10" in RobocopyOptions(retry_wait_seconds=10).to_args()


# ── Boolean flags ────────────────────────────────────────────────────────────


class TestBooleanFlags:
    @pytest.mark.parametrize(
        "field, expected_flag",
        [
            ("subdirectories", "/S"),
            ("subdirectories_including_empty", "/E"),
            ("restart_mode", "/Z"),
            ("unbuffered_io", "/J"),
            ("mirror", "/MIR"),
            ("move_files", "/MOV"),
            ("move_files_and_dirs", "/MOVE"),
            ("verbose", "/V"),
            ("no_progress", "/NP"),
            ("list_only", "/L"),
            ("no_file_list", "/NFL"),
            ("no_directory_list", "/NDL"),
            ("no_file_sizes", "/NFS"),
            ("exclude_changed_files", "/XC"),
            ("exclude_newer_files", "/XN"),
            ("exclude_older_files", "/XO"),
            ("exclude_extra_files_dirs", "/XX"),
            ("exclude_lonely_files_dirs", "/XL"),
            ("include_same_files", "/IS"),
            ("include_tweaked_files", "/IT"),
            ("purge_destination", "/PURGE"),
            ("timestamp_output", "/TS"),
            ("estimate_time", "/ETA"),
        ],
    )
    def test_flag(self, field, expected_flag):
        assert expected_flag in RobocopyOptions(**{field: True}).to_args()


# ── Integer flags ────────────────────────────────────────────────────────────


class TestIntegerFlags:
    def test_levels(self):
        assert "/LEV:3" in RobocopyOptions(levels=3).to_args()

    def test_multithread(self):
        assert "/MT:8" in RobocopyOptions(multithread=8).to_args()

    def test_maximum_file_size(self):
        assert "/MAX:1024" in RobocopyOptions(maximum_file_size=1024).to_args()

    def test_minimum_file_size(self):
        assert "/MIN:512" in RobocopyOptions(minimum_file_size=512).to_args()

    def test_maximum_file_age_days(self):
        assert "/MAXAGE:7" in RobocopyOptions(maximum_file_age_days=7).to_args()

    def test_minimum_file_age_days(self):
        assert "/MINAGE:1" in RobocopyOptions(minimum_file_age_days=1).to_args()


# ── String flags ─────────────────────────────────────────────────────────────


class TestStringFlags:
    def test_include_attributes(self):
        assert "/IA:RA" in RobocopyOptions(include_attributes="RA").to_args()

    def test_exclude_attributes(self):
        assert "/XA:SH" in RobocopyOptions(exclude_attributes="SH").to_args()

    def test_job_name(self):
        assert "/JOB:myjob" in RobocopyOptions(job_name="myjob").to_args()


# ── List flags ───────────────────────────────────────────────────────────────


class TestListFlags:
    def test_exclude_files(self):
        args = RobocopyOptions(exclude_files=["*.tmp", "*.log"]).to_args()
        idx = args.index("/XF")
        assert args[idx + 1] == "*.tmp"
        assert args[idx + 2] == "*.log"

    def test_exclude_directories(self):
        args = RobocopyOptions(exclude_directories=["temp", "cache"]).to_args()
        idx = args.index("/XD")
        assert args[idx + 1] == "temp"
        assert args[idx + 2] == "cache"

    def test_exclude_files_single(self):
        args = RobocopyOptions(exclude_files=["*.bak"]).to_args()
        assert "/XF" in args
        assert "*.bak" in args


# ── Log file handling ────────────────────────────────────────────────────────


class TestLogFile:
    def test_log_file_string(self):
        assert "/LOG:output.log" in RobocopyOptions(log_file="output.log").to_args()

    def test_log_file_path(self):
        args = RobocopyOptions(log_file=Path("output.log")).to_args()
        assert any(a.startswith("/LOG:") for a in args)

    def test_append_uses_log_plus_prefix(self):
        args = RobocopyOptions(log_file="output.log", append_to_log=True).to_args()
        assert "/LOG+:output.log" in args
        assert "/LOG:output.log" not in args

    def test_append_without_log_file_produces_nothing(self):
        args = RobocopyOptions(append_to_log=True).to_args()
        assert not any(a.startswith("/LOG") for a in args)


# ── /COPY: flag composition ──────────────────────────────────────────────────


class TestCopyFlags:
    def _copy_flags(self, args):
        arg = next((a for a in args if a.startswith("/COPY:")), None)
        return arg.split(":", 1)[1] if arg else ""

    def test_copy_data_only(self):
        flags = self._copy_flags(RobocopyOptions(copy_data_only=True).to_args())
        assert "D" in flags

    def test_copy_data_attributes(self):
        flags = self._copy_flags(RobocopyOptions(copy_data_attributes=True).to_args())
        assert "D" in flags
        assert "A" in flags

    def test_copy_data_attributes_timestamps(self):
        flags = self._copy_flags(RobocopyOptions(copy_data_attributes_timestamps=True).to_args())
        assert "D" in flags
        assert "A" in flags
        assert "T" in flags

    def test_copy_security_ownership_audit(self):
        opts = RobocopyOptions(copy_security=True, copy_ownership=True, copy_audit=True)
        flags = self._copy_flags(opts.to_args())
        assert "S" in flags
        assert "O" in flags
        assert "U" in flags

    def test_copy_all_file_info_suppresses_copy_subflags(self):
        args = RobocopyOptions(copy_all_file_info=True, copy_data_only=True).to_args()
        assert "/COPYALL" in args
        assert not any(a.startswith("/COPY:") for a in args)

    def test_copy_all_suppresses_copy_subflags(self):
        args = RobocopyOptions(copy_all=True, copy_data_only=True).to_args()
        # /COPY:ALL should appear, but /COPY:D (from copy_flags) should not
        assert not any(a == "/COPY:D" for a in args)


# ── Mirror / purge interaction ───────────────────────────────────────────────


class TestMirrorPurge:
    def test_mirror_suppresses_purge(self):
        args = RobocopyOptions(mirror=True, purge_destination=True).to_args()
        assert "/MIR" in args
        assert "/PURGE" not in args

    def test_purge_without_mirror_included(self):
        assert "/PURGE" in RobocopyOptions(purge_destination=True).to_args()


# ── dry_run / list_only ──────────────────────────────────────────────────────


class TestDryRun:
    def test_dry_run_adds_list_flag(self):
        assert "/L" in RobocopyOptions(dry_run=True).to_args()

    def test_dry_run_with_list_only_no_duplicate_flag(self):
        args = RobocopyOptions(dry_run=True, list_only=True).to_args()
        assert args.count("/L") == 1

    def test_list_only_alone_adds_flag(self):
        assert "/L" in RobocopyOptions(list_only=True).to_args()


# ── robocopy() function ──────────────────────────────────────────────────────


class TestRobocopyFunction:
    @patch("bellhop_trolley.shims.robocopy.subprocess.run")
    def test_command_starts_with_robocopy(self, mock_run):
        mock_run.return_value = _completed(0)
        robocopy("C:\\src", "D:\\dst")
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "robocopy"

    @patch("bellhop_trolley.shims.robocopy.subprocess.run")
    def test_source_and_destination_positions(self, mock_run):
        mock_run.return_value = _completed(0)
        robocopy("C:\\src", "D:\\dst")
        cmd = mock_run.call_args[0][0]
        assert cmd[1] == "C:\\src"
        assert cmd[2] == "D:\\dst"

    @patch("bellhop_trolley.shims.robocopy.subprocess.run")
    def test_default_file_pattern_is_all(self, mock_run):
        mock_run.return_value = _completed(0)
        robocopy("C:\\src", "D:\\dst")
        assert mock_run.call_args[0][0][3] == "*.*"

    @patch("bellhop_trolley.shims.robocopy.subprocess.run")
    def test_custom_file_pattern(self, mock_run):
        mock_run.return_value = _completed(0)
        robocopy("C:\\src", "D:\\dst", files="*.txt")
        assert mock_run.call_args[0][0][3] == "*.txt"

    @patch("bellhop_trolley.shims.robocopy.subprocess.run")
    def test_path_objects_stringified(self, mock_run):
        mock_run.return_value = _completed(0)
        robocopy(Path("C:\\src"), Path("D:\\dst"))
        cmd = mock_run.call_args[0][0]
        assert cmd[1] == "C:\\src"
        assert cmd[2] == "D:\\dst"

    @patch("bellhop_trolley.shims.robocopy.subprocess.run")
    def test_options_forwarded_to_command(self, mock_run):
        mock_run.return_value = _completed(0)
        robocopy("C:\\src", "D:\\dst", subdirectories=True, verbose=True)
        cmd = mock_run.call_args[0][0]
        assert "/S" in cmd
        assert "/V" in cmd

    @patch("bellhop_trolley.shims.robocopy.subprocess.run")
    def test_returns_completed_process(self, mock_run):
        expected = _completed(1)
        mock_run.return_value = expected
        assert robocopy("C:\\src", "D:\\dst") is expected

    @patch("bellhop_trolley.shims.robocopy.subprocess.run")
    def test_subprocess_run_called_with_check_false(self, mock_run):
        mock_run.return_value = _completed(0)
        robocopy("C:\\src", "D:\\dst")
        assert mock_run.call_args[1].get("check") is False

    @patch("bellhop_trolley.shims.robocopy.subprocess.run")
    def test_subprocess_run_called_with_capture_output(self, mock_run):
        mock_run.return_value = _completed(0)
        robocopy("C:\\src", "D:\\dst")
        assert mock_run.call_args[1].get("capture_output") is True

    @pytest.mark.parametrize("code", range(8))
    @patch("bellhop_trolley.shims.robocopy.subprocess.run")
    def test_exit_codes_0_to_7_do_not_raise(self, mock_run, code):
        mock_run.return_value = _completed(code)
        result = robocopy("C:\\src", "D:\\dst")
        assert result.returncode == code

    @pytest.mark.parametrize("code", [8, 9, 16])
    @patch("bellhop_trolley.shims.robocopy.subprocess.run")
    def test_exit_code_8_and_above_raises(self, mock_run, code):
        mock_run.return_value = _completed(code)
        with pytest.raises(subprocess.CalledProcessError) as exc_info:
            robocopy("C:\\src", "D:\\dst")
        assert exc_info.value.returncode == code

    @patch("bellhop_trolley.shims.robocopy.subprocess.run")
    def test_file_not_found_propagates(self, mock_run):
        mock_run.side_effect = FileNotFoundError("robocopy not found")
        with pytest.raises(FileNotFoundError):
            robocopy("C:\\src", "D:\\dst")


# ── mirror_directories() ─────────────────────────────────────────────────────


class TestMirrorDirectories:
    @patch("bellhop_trolley.shims.robocopy.subprocess.run")
    def test_includes_mir_flag(self, mock_run):
        mock_run.return_value = _completed(0)
        mirror_directories("C:\\src", "D:\\dst")
        assert "/MIR" in mock_run.call_args[0][0]

    @patch("bellhop_trolley.shims.robocopy.subprocess.run")
    def test_verbose_by_default(self, mock_run):
        mock_run.return_value = _completed(0)
        mirror_directories("C:\\src", "D:\\dst")
        assert "/V" in mock_run.call_args[0][0]

    @patch("bellhop_trolley.shims.robocopy.subprocess.run")
    def test_log_file_forwarded(self, mock_run):
        mock_run.return_value = _completed(0)
        mirror_directories("C:\\src", "D:\\dst", log_file="mirror.log")
        cmd = mock_run.call_args[0][0]
        assert any(a.startswith("/LOG:") for a in cmd)

    @patch("bellhop_trolley.shims.robocopy.subprocess.run")
    def test_purge_not_duplicated_when_mirror_set(self, mock_run):
        mock_run.return_value = _completed(0)
        mirror_directories("C:\\src", "D:\\dst")
        assert "/PURGE" not in mock_run.call_args[0][0]


# ── sync_directories() ───────────────────────────────────────────────────────


class TestSyncDirectories:
    @patch("bellhop_trolley.shims.robocopy.subprocess.run")
    def test_includes_subdirectories_flag(self, mock_run):
        mock_run.return_value = _completed(0)
        sync_directories("C:\\src", "D:\\dst")
        assert "/S" in mock_run.call_args[0][0]

    @patch("bellhop_trolley.shims.robocopy.subprocess.run")
    def test_excludes_older_files_by_default(self, mock_run):
        mock_run.return_value = _completed(0)
        sync_directories("C:\\src", "D:\\dst")
        assert "/XO" in mock_run.call_args[0][0]

    @patch("bellhop_trolley.shims.robocopy.subprocess.run")
    def test_exclude_older_can_be_disabled(self, mock_run):
        mock_run.return_value = _completed(0)
        sync_directories("C:\\src", "D:\\dst", exclude_older=False)
        assert "/XO" not in mock_run.call_args[0][0]

    @patch("bellhop_trolley.shims.robocopy.subprocess.run")
    def test_log_file_forwarded(self, mock_run):
        mock_run.return_value = _completed(0)
        sync_directories("C:\\src", "D:\\dst", log_file="sync.log")
        cmd = mock_run.call_args[0][0]
        assert any(a.startswith("/LOG:") for a in cmd)


# ── backup_with_retry() ──────────────────────────────────────────────────────


class TestBackupWithRetry:
    @patch("bellhop_trolley.shims.robocopy.subprocess.run")
    def test_includes_restart_and_backup_mode(self, mock_run):
        mock_run.return_value = _completed(0)
        backup_with_retry("C:\\src", "D:\\dst")
        assert "/ZB" in mock_run.call_args[0][0]

    @patch("bellhop_trolley.shims.robocopy.subprocess.run")
    def test_includes_subdirectories_flag(self, mock_run):
        mock_run.return_value = _completed(0)
        backup_with_retry("C:\\src", "D:\\dst")
        assert "/S" in mock_run.call_args[0][0]

    @patch("bellhop_trolley.shims.robocopy.subprocess.run")
    def test_default_retry_count_5_included(self, mock_run):
        mock_run.return_value = _completed(0)
        backup_with_retry("C:\\src", "D:\\dst")
        assert "/R:5" in mock_run.call_args[0][0]

    @patch("bellhop_trolley.shims.robocopy.subprocess.run")
    def test_custom_retry_count(self, mock_run):
        mock_run.return_value = _completed(0)
        backup_with_retry("C:\\src", "D:\\dst", retry_count=3)
        assert "/R:3" in mock_run.call_args[0][0]

    @patch("bellhop_trolley.shims.robocopy.subprocess.run")
    def test_custom_retry_wait(self, mock_run):
        mock_run.return_value = _completed(0)
        backup_with_retry("C:\\src", "D:\\dst", retry_wait_seconds=60)
        assert "/W:60" in mock_run.call_args[0][0]

    @patch("bellhop_trolley.shims.robocopy.subprocess.run")
    def test_default_retry_wait_30_suppressed(self, mock_run):
        mock_run.return_value = _completed(0)
        backup_with_retry("C:\\src", "D:\\dst")
        assert "/W:30" not in mock_run.call_args[0][0]
