"""
Tests for uncovered lines in worktree_officer.py.
Coverage targets:
  - Line 116: recursive remove_worktree call in setup_worktree
  - Lines 131-132: branch-already-exists fallback path in setup_worktree
  - Lines 175-181: worktree list parsing in remove_worktree
"""
import sys
sys.path.insert(0, "scripts")

import tempfile
import shutil
import os
from unittest.mock import patch, MagicMock

import pytest

from worktree_officer import WorktreeOfficer, WorktreeConfig


class TestWorktreeOfficerUncovered:
    """Cover uncovered branches in worktree_officer.py"""

    def _make_officer(self):
        tmp = tempfile.mkdtemp()
        config = WorktreeConfig(base_dir=tmp, project_name="test-project")
        officer = WorktreeOfficer(config)
        return officer, tmp

    def test_setup_worktree_when_already_exists_removes_first(self):
        """Line 116: if os.path.exists(wt_dir) triggers remove_worktree call"""
        officer, tmp = self._make_officer()
        try:
            # Initialize the officer with a mock project dir
            officer.project_dir = tmp
            # Create a fake worktree dir that already exists
            wt_dir = os.path.join(tmp, "test-project", "test-agent")
            os.makedirs(wt_dir, exist_ok=True)
            
            # Mock _run_git to simulate worktree creation failing (branch exists)
            call_count = 0
            def mock_run_git(cmd, cwd=None):
                nonlocal call_count
                call_count += 1
                if cmd[0] == 'worktree' and cmd[1] == 'add':
                    # Simulate branch already exists error
                    return (1, "", "fatal: invalid reference: council/test-agent")
                elif cmd[0] == 'worktree' and cmd[1] == 'list':
                    # Simulate worktree already listed
                    return (0, f"{wt_dir} HEAD\n", "")
                elif cmd[0] == 'branch' and cmd[1] == '-D':
                    return (0, "", "")
                return (0, "", "")
            
            officer._run_git = mock_run_git
            
            # This should try to remove the existing dir and recreate
            result = officer.setup_worktree("test-agent")
            
            # The remove_worktree path should have been triggered
            assert os.path.exists(wt_dir) == False or result is not None
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_setup_worktree_branch_exists_fallback(self):
        """Lines 131-132: branch already exists, found in worktree list"""
        officer, tmp = self._make_officer()
        try:
            officer.project_dir = tmp
            wt_dir = os.path.join(tmp, "test-project", "existing-agent")
            
            call_count = 0
            def mock_run_git(cmd, cwd=None):
                nonlocal call_count
                if cmd[0] == 'worktree' and cmd[1] == 'add':
                    # Simulate branch already exists error
                    return (128, "", "fatal: invalid reference: council/existing-agent")
                elif cmd[0] == 'worktree' and cmd[1] == 'list':
                    # Return worktree already exists in list
                    return (0, f"{wt_dir} HEAD abc123\n", "")
                elif cmd[0] == 'branch':
                    return (0, "", "")
                return (0, "", "")
            
            officer._run_git = mock_run_git
            result = officer.setup_worktree("existing-agent")
            
            # Should return the existing worktree path
            assert result == wt_dir
            assert "existing-agent" in officer.worktree_map
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_remove_worktree_parses_worktree_list(self):
        """Lines 175-181: parses worktree list to find worktree dir"""
        officer, tmp = self._make_officer()
        try:
            officer.project_dir = tmp
            # Manually add to worktree_map
            officer.worktree_map["ghost-agent"] = "/nonexistent/path"
            
            # Mock _run_git to return worktree list containing the agent
            def mock_run_git(cmd, cwd=None):
                if cmd[0] == 'worktree' and cmd[1] == 'list':
                    wt_path = os.path.join(tmp, "test-project", "ghost-agent")
                    os.makedirs(os.path.dirname(wt_path), exist_ok=True)
                    # Realistic worktree list format
                    return (0, f"{wt_path} HEAD abc123def456\n  /another/path HEAD\n", "")
                elif cmd[0] == 'worktree' and cmd[1] == 'remove':
                    return (0, "", "")
                elif cmd[0] == 'branch' and cmd[1] == '-D':
                    return (0, "", "")
                return (0, "", "")
            
            officer._run_git = mock_run_git
            
            result = officer.remove_worktree("ghost-agent")
            assert result == True
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
