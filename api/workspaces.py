from __future__ import annotations
import hashlib
import json
import re
import secrets
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from api.auth import current_user
from api.db import connect
from api.permissions import membership, require_roles
from api.rbac import require_action

router = APIRouter(prefix='/api', tags=['workspaces'])


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    timezone: str = 'Europe/Moscow'


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    timezone: str | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=8)


class InviteCreate(BaseModel):
    role: str = 'viewer'
    max_uses: int | None = Field(default=None, ge=1, le=1000)
    expires_in_days: int | None = Field(default=7, ge=1, le=90)
    channel_scope: list[int] | None = None


class InviteAccept(BaseModel):
    token: str = Field(min_length=8, max_length=256)


def slugify(name: str) -> str:
    base = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-') or 'workspace'
    return f'{base}-{secrets.token_hex(3)}'


def audit(cur, wid, uid, action, entity, eid=None, details='{}'):
    cur.execute('INSERT INTO cd_audit_log(workspace_id,user_id,action,entity_type,entity_id,details) VALUES(%s,%s,%s,%s,%s,%s::jsonb)',
                (wid, uid, action, entity, eid, details))


@router.get('/workspaces')
def list_workspaces(user: dict = Depends(current_user)):
    with connect() as conn, conn.cursor() as cur:
        cur.execute('''SELECT w.*,m.role,m.channel_scope FROM cd_workspaces w JOIN cd_workspace_members m ON m.workspace_id=w.id
        WHERE m.user_id=%s AND m.status='active' AND w.is_active=true ORDER BY w.updated_at DESC''', (user['id'],))
        return cur.fetchall()


@router.post('/workspaces', status_code=201)
def create_workspace(payload: WorkspaceCreate, user: dict = Depends(current_user)):
    with connect() as conn, conn.cursor() as cur:
        cur.execute('''INSERT INTO cd_workspaces(name,slug,owner_user_id,timezone) VALUES(%s,%s,%s,%s) RETURNING *''',
                    (payload.name.strip(), slugify(payload.name), user['id'], payload.timezone))
        ws = cur.fetchone()
        cur.execute("INSERT INTO cd_workspace_members(workspace_id,user_id,role) VALUES(%s,%s,'owner')", (ws['id'], user['id']))
        audit(cur, ws['id'], user['id'], 'workspace.created', 'workspace', ws['id'])
        return {**ws, 'role': 'owner', 'channel_scope': []}


@router.get('/workspaces/{workspace_id}')
def get_workspace(workspace_id: int, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'workspace.view')
    with connect() as conn, conn.cursor() as cur:
        cur.execute('SELECT * FROM cd_workspaces WHERE id=%s AND is_active=true', (workspace_id,))
        ws = cur.fetchone()
    if not ws:
        raise HTTPException(404, 'Рабочее пространство не найдено')
    return {**ws, 'role': member['role'], 'channel_scope': member['channel_scope']}


@router.patch('/workspaces/{workspace_id}')
def update_workspace(workspace_id: int, payload: WorkspaceUpdate, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_roles(member, 'owner', 'admin')
    data = payload.model_dump(exclude_none=True)
    if not data:
        return get_workspace(workspace_id, user)
    fields = []
    values = []
    for key in ('name', 'timezone', 'currency'):
        if key in data:
            fields.append(f'{key}=%s')
            values.append(data[key])
    values.extend([workspace_id])
    with connect() as conn, conn.cursor() as cur:
        cur.execute(f"UPDATE cd_workspaces SET {','.join(fields)},updated_at=now() WHERE id=%s RETURNING *", values)
        ws = cur.fetchone()
        audit(cur, workspace_id, user['id'], 'workspace.updated', 'workspace', workspace_id)
        return {**ws, 'role': member['role'], 'channel_scope': member['channel_scope']}


@router.get('/workspaces/{workspace_id}/members')
def members(workspace_id: int, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'members.view')
    with connect() as conn, conn.cursor() as cur:
        cur.execute('''SELECT m.id,m.role,m.status,m.channel_scope,m.joined_at,u.telegram_id,u.username,u.first_name,u.last_name
        FROM cd_workspace_members m JOIN cd_users u ON u.id=m.user_id WHERE m.workspace_id=%s ORDER BY m.joined_at''', (workspace_id,))
        return cur.fetchall()


@router.post('/workspaces/{workspace_id}/invites', status_code=201)
def create_invite(workspace_id: int, payload: InviteCreate, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'invite.create')
    allowed = {'admin', 'editor', 'author', 'designer', 'ad_manager', 'analyst', 'viewer'}
    if payload.role not in allowed:
        raise HTTPException(422, 'Недопустимая роль')
    token = secrets.token_urlsafe(24)
    digest = hashlib.sha256(token.encode()).hexdigest()
    scope = json.dumps(payload.channel_scope or [])
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""INSERT INTO cd_invites(workspace_id,token_hash,role,channel_scope,max_uses,expires_at,created_by)
        VALUES(%s,%s,%s,%s::jsonb,%s,CASE WHEN %s IS NULL THEN NULL ELSE now()+(%s*interval '1 day') END,%s)
        RETURNING id,role,channel_scope,max_uses,expires_at""",
                    (workspace_id, digest, payload.role, scope, payload.max_uses, payload.expires_in_days,
                     payload.expires_in_days, user['id']))
        row = cur.fetchone()
        audit(cur, workspace_id, user['id'], 'invite.created', 'invite', row['id'])
    return {**row, 'token': token}


@router.post('/invites/accept')
def accept_invite(payload: InviteAccept, user: dict = Depends(current_user)):
    digest = hashlib.sha256(payload.token.strip().encode()).hexdigest()
    with connect() as conn, conn.cursor() as cur:
        cur.execute('''SELECT i.id AS invite_id,i.role AS invite_role,i.channel_scope AS invite_scope,i.max_uses,i.used_count,i.expires_at,
        i.workspace_id,w.name AS workspace_name,w.slug,w.timezone,w.currency
        FROM cd_invites i JOIN cd_workspaces w ON w.id=i.workspace_id
        WHERE i.token_hash=%s AND i.is_active=true''', (digest,))
        invite = cur.fetchone()
        if not invite:
            raise HTTPException(404, 'Приглашение не найдено или отключено')
        if invite['expires_at'] and invite['expires_at'] < datetime.now(timezone.utc):
            raise HTTPException(410, 'Срок действия приглашения истёк')
        if invite['max_uses'] is not None and invite['used_count'] >= invite['max_uses']:
            raise HTTPException(410, 'Приглашение исчерпано')

        cur.execute('SELECT id,status,role FROM cd_workspace_members WHERE workspace_id=%s AND user_id=%s',
                    (invite['workspace_id'], user['id']))
        existing = cur.fetchone()
        scope = json.dumps(invite.get('invite_scope') or [])
        if existing and existing['status'] == 'active':
            raise HTTPException(409, 'Вы уже являетесь участником этого рабочего пространства')
        if existing:
            cur.execute("""UPDATE cd_workspace_members SET role=%s,channel_scope=%s::jsonb,status='active',invited_by=%s,updated_at=now()
            WHERE id=%s RETURNING id,role,channel_scope""", (invite['invite_role'], scope, user['id'], existing['id']))
        else:
            cur.execute("""INSERT INTO cd_workspace_members(workspace_id,user_id,role,channel_scope,invited_by)
            VALUES(%s,%s,%s,%s::jsonb,%s) RETURNING id,role,channel_scope""",
                        (invite['workspace_id'], user['id'], invite['invite_role'], scope, user['id']))
        member = cur.fetchone()
        cur.execute('UPDATE cd_invites SET used_count=used_count+1 WHERE id=%s', (invite['invite_id'],))
        audit(cur, invite['workspace_id'], user['id'], 'member.joined', 'member', member['id'], json.dumps({'role': member['role']}))
    return {'workspace_id': invite['workspace_id'], 'workspace_name': invite['workspace_name'], 'slug': invite['slug'],
            'timezone': invite['timezone'], 'currency': invite['currency'], 'role': member['role'],
            'channel_scope': member['channel_scope']}


@router.get('/workspaces/{workspace_id}/audit')
def workspace_audit(workspace_id: int, limit: int = 50, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'audit.view')
    limit = max(1, min(limit, 200))
    with connect() as conn, conn.cursor() as cur:
        cur.execute('''SELECT id,user_id,action,entity_type,entity_id,details,created_at
        FROM cd_audit_log WHERE workspace_id=%s ORDER BY created_at DESC LIMIT %s''', (workspace_id, limit))
        return cur.fetchall()
