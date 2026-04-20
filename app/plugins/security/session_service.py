import uuid
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from app.core.db import AsyncSessionFactory as async_session, get_async_db
from .models import UserSession
from fastapi import Request


class SessionManager:
    def __init__(self, secret_key: str):
        self.cipher = Fernet(secret_key)
        self.token_rotation_interval = timedelta(minutes=15)

    async def create_session(self, user_id: str, request: Request) -> tuple[UserSession, str]:
      async with async_session() as session:
          session_token = str(uuid.uuid4())
          encrypted_token = self.cipher.encrypt(session_token.encode())
          
          new_session = UserSession(
              id=session_token,
              user_id=user_id,
              ip_address=request.client.host,
              user_agent=request.headers.get("User-Agent"),
              expires_at=datetime.utcnow() + timedelta(hours=1),
              mfa_authenticated=False
          )
          
          session.add(new_session)
          await session.commit()
          
          return new_session, encrypted_token.decode()  # Returns both

    async def validate_session(self, encrypted_token: str) -> tuple[UserSession, str]:
      try:
          decrypted_token = self.cipher.decrypt(encrypted_token.encode()).decode()
      except:
          raise ValueError("Token invalide")
      
      async with async_session() as session:
          user_session = await session.get(UserSession, decrypted_token)
          
          if not user_session or user_session.expires_at < datetime.utcnow():
              raise PermissionError("Session expirée")
              
          if datetime.utcnow() > user_session.created_at + self.token_rotation_interval:
              await session.delete(user_session)
              new_session, new_token = await self.create_session(user_session.user_id, request)
              return new_session, new_token  # Returns the new session + token
          
          user_session.refresh_count += 1
          await session.commit()
          return user_session, encrypted_token  # Keeps the original token