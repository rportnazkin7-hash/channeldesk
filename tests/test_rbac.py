import pytest
from fastapi import HTTPException

from api.rbac import MATRIX, require_action


def test_every_role_can_view_workspace():
    for role in MATRIX['workspace.view']:
        require_action({'role': role}, 'workspace.view')  # не должно бросать


def test_owner_and_admin_can_connect_channel():
    require_action({'role': 'owner'}, 'channel.connect')
    require_action({'role': 'admin'}, 'channel.connect')


def test_viewer_cannot_connect_channel():
    with pytest.raises(HTTPException) as exc:
        require_action({'role': 'viewer'}, 'channel.connect')
    assert exc.value.status_code == 403


def test_author_cannot_create_invite():
    with pytest.raises(HTTPException) as exc:
        require_action({'role': 'author'}, 'invite.create')
    assert exc.value.status_code == 403


def test_analyst_can_view_audit_but_author_cannot():
    require_action({'role': 'analyst'}, 'audit.view')
    with pytest.raises(HTTPException) as exc:
        require_action({'role': 'author'}, 'audit.view')
    assert exc.value.status_code == 403


def test_unknown_action_is_500():
    with pytest.raises(HTTPException) as exc:
        require_action({'role': 'owner'}, 'does.not.exist')
    assert exc.value.status_code == 500
