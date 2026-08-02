from __future__ import annotations
from fastapi import HTTPException
from api.db import connect

ROLE_LEVEL={'viewer':0,'analyst':1,'designer':1,'author':1,'ad_manager':2,'editor':2,'admin':3,'owner':4}

def membership(user_id:int,workspace_id:int,minimum:str='viewer')->dict:
    with connect() as conn,conn.cursor() as cur:
        cur.execute('''SELECT * FROM cd_workspace_members WHERE workspace_id=%s AND user_id=%s AND status='active' ''',(workspace_id,user_id))
        row=cur.fetchone()
    if not row: raise HTTPException(403,'Нет доступа к рабочему пространству')
    if ROLE_LEVEL.get(row['role'],-1)<ROLE_LEVEL.get(minimum,99): raise HTTPException(403,'Недостаточно прав')
    return row

def require_roles(member:dict,*roles:str)->None:
    if member.get('role') not in roles: raise HTTPException(403,'Недостаточно прав')
