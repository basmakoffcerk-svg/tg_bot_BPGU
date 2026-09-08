"""
Vercel Serverless Entrypoint for ARM Starosta.
"""
from app.api.app import app

# Vercel ASGI Handler
handler = app
