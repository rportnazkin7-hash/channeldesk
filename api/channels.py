from __future__ import annotations
import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from api.auth import current_user
from api.db import connect
from api.permissions import membership
from api.rbac import require_action
from api.telegram import verify_bot_permissions

router = APIRouter(prefix='/api', tags=['channels'])


class ConnectChannel(BaseModel):
    connection_id: int


@router.get('/channel-connections/pending')
def pending_connections(user: dict = Depends(current_user)):
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT id,telegram_chat_id,title,username,bot_permissions,observed_at
        FROM cd_channel_connections WHERE actor_telegram_id=%s AND status='pending' ORDER BY updated_at DESC""",
                    (user['telegram_id'],))
        return cur.fetchall()


@router.get('/workspaces/{workspace_id}/channels')
def list_channels(workspace_id: int, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'channel.view')
    with connect() as conn, conn.cursor() as cur:
        cur.execute('SELECT * FROM cd_channels WHERE workspace_id=%s AND is_active=true ORDER BY title', (workspace_id,))
        return cur.fetchall()


@router.post('/workspaces/{workspace_id}/channels/connect', status_code=201)
def connect_channel(workspace_id: int, payload: ConnectChannel, user: dict = Depends(current_user)):
    member = membership(user['id'], workspace_id)
    require_action(member, 'channel.connect')
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT * FROM cd_channel_connections WHERE id=%s AND actor_telegram_id=%s AND status='pending' FOR UPDATE""",
                    (payload.connection_id, user['telegram_id']))
        pending = cur.fetchone()
        if not pending:
            raise HTTPException(404, 'Канал не найден. Переустановите права бота в канале')

        # Live-проверка прав непосредственно перед подключением (Этап A).
        permissions = dict(pending.get('bot_permissions') or {})
        live = verify_bot_permissions(pending['telegram_chat_id'])
        if live is None:
            # Проверка недоступна (dev-режим без BOT_TOKEN или сбой Telegram) —
            # доверяем правам, сохранённым при событии my_chat_member.
            if not permissions.get('can_post_messages'):
                raise HTTPException(422, 'Боту не выдано право публикации сообщений')
        else:
            if not live['is_admin']:
                raise HTTPException(422, 'Бот не является администратором канала. Добавьте бота в администраторы и попробуйте снова.')
            if not live['can_post_messages']:
                raise HTTPException(422, 'Боту не выдано право публикации сообщений')
            permissions = live['permissions']

        cur.execute('SELECT id,workspace_id FROM cd_channels WHERE telegram_chat_id=%s', (pending['telegram_chat_id'],))
        existing = cur.fetchone()
        if existing and existing['workspace_id'] != workspace_id:
            raise HTTPException(409, 'Канал уже подключён к другому рабочему пространству')
        if existing:
            cur.execute("""UPDATE cd_channels SET title=%s,username=%s,bot_permissions=%s::jsonb,is_connected=true,is_active=true,
            connected_by=%s,connected_at=now(),updated_at=now() WHERE id=%s RETURNING *""",
                        (pending['title'], pending['username'], json.dumps(permissions), user['id'], existing['id']))
        else:
            cur.execute("""INSERT INTO cd_channels(workspace_id,telegram_chat_id,title,username,bot_permissions,is_connected,connected_by,connected_at)
            VALUES(%s,%s,%s,%s,%s::jsonb,true,%s,now()) RETURNING *""",
                        (workspace_id, pending['telegram_chat_id'], pending['title'], pending['username'],
                         json.dumps(permissions), user['id']))
        channel = cur.fetchone()
        cur.execute("UPDATE cd_channel_connections SET status='connected',connected_channel_id=%s,updated_at=now() WHERE id=%s",
                    (channel['id'], pending['id']))
        cur.execute("""INSERT INTO cd_audit_log(workspace_id,user_id,action,entity_type,entity_id,details)
        VALUES(%s,%s,'channel.connected','channel',%s,%s::jsonb)""",
                    (workspace_id, user['id'], channel['id'], '{}'))
        return channel
