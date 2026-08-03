from __future__ import annotations
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.workspaces import router as workspaces_router
from api.channels import router as channels_router

app = FastAPI(title='ChannelDesk API', version='0.5.0')
origins=[x.strip() for x in os.getenv('ALLOWED_ORIGINS','http://localhost:5173').split(',') if x.strip()]
app.add_middleware(CORSMiddleware,allow_origins=origins,allow_credentials=False,allow_methods=['GET','POST','PATCH','DELETE','OPTIONS'],allow_headers=['Content-Type','X-Telegram-Init-Data','X-Dev-Api-Key'])
app.include_router(workspaces_router)
app.include_router(channels_router)

@app.get('/api/health')
def health():
    return {'ok': True, 'service': 'ChannelDesk API', 'version': '0.5.0'}
