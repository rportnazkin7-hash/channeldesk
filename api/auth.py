from __future__ import annotations
import hashlib,hmac,json,os
from time import time
from urllib.parse import parse_qsl
from fastapi import Header,HTTPException
from api.db import connect

MAX_INIT_DATA_AGE=86400

def validate_init_data(raw: str) -> dict:
    if not raw: raise HTTPException(401,'Откройте ChannelDesk из Telegram')
    pairs=dict(parse_qsl(raw,keep_blank_values=True)); received=pairs.pop('hash',None)
    if not received: raise HTTPException(401,'Telegram hash is missing')
    try: auth_date=int(pairs.get('auth_date','0'))
    except ValueError: raise HTTPException(401,'Invalid auth date')
    if not auth_date or time()-auth_date>MAX_INIT_DATA_AGE: raise HTTPException(401,'Telegram session expired')
    token=os.getenv('BOT_TOKEN','').strip()
    if not token: raise HTTPException(503,'BOT_TOKEN is not configured')
    check='\n'.join(f'{k}={v}' for k,v in sorted(pairs.items()))
    secret=hmac.new(b'WebAppData',token.encode(),hashlib.sha256).digest()
    calculated=hmac.new(secret,check.encode(),hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calculated,received): raise HTTPException(401,'Invalid Telegram signature')
    try: user=json.loads(pairs.get('user','{}'))
    except json.JSONDecodeError: raise HTTPException(401,'Invalid Telegram user')
    if not user.get('id'): raise HTTPException(401,'Telegram user id is missing')
    return user

def current_user(x_telegram_init_data: str|None=Header(default=None),x_dev_api_key: str|None=Header(default=None)) -> dict:
    expected=os.getenv('DEV_API_KEY','').strip()
    if expected and x_dev_api_key and hmac.compare_digest(expected,x_dev_api_key):
        tg={'id':123456789,'username':'developer','first_name':'Developer','last_name':None}
    else: tg=validate_init_data(x_telegram_init_data or '')
    with connect() as conn, conn.cursor() as cur:
        cur.execute('''INSERT INTO cd_users(telegram_id,username,first_name,last_name,last_seen_at)
        VALUES(%s,%s,%s,%s,now()) ON CONFLICT(telegram_id) DO UPDATE SET username=excluded.username,
        first_name=excluded.first_name,last_name=excluded.last_name,last_seen_at=now(),updated_at=now() RETURNING *''',
        (int(tg['id']),tg.get('username'),tg.get('first_name'),tg.get('last_name')))
        return cur.fetchone()
