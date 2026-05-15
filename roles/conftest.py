# ------------------------------------------------------------------------------
# File        : ctlabs-ansible/roles/conftest.py
# Description : shared pytest fixtures for role tests
# ------------------------------------------------------------------------------

import os
import pytest


@pytest.fixture(scope="module")
def role_dir(request):
    return os.path.normpath(os.path.join(os.path.dirname(str(request.fspath)), ".."))


@pytest.fixture(scope="session")
def ansible_repo_root():
    return os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
