"""Autenticação do WebSocket: o JWT de acesso vem na query string (`?token=<access>`).

Evite logar URLs de WebSocket, já que o token vai nelas.
"""

import logging
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken

logger = logging.getLogger("chat")


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        scope["user"] = await self.get_user(scope)

        return await super().__call__(scope, receive, send)

    @database_sync_to_async
    def get_user(self, scope):
        User = get_user_model()

        try:
            token = self._get_token(scope)

            if not token:
                logger.warning("WS recusado: conexão sem token.")

                return AnonymousUser()

            user_id = AccessToken(token).get("user_id")

            if not user_id:
                logger.warning("WS recusado: token sem user_id.")

                return AnonymousUser()

            return User.objects.get(id=user_id, is_active=True)

        except (InvalidToken, TokenError) as error:
            # Nunca loga o token, só o motivo.
            logger.warning("WS recusado: token inválido ou expirado (%s).", error)

            return AnonymousUser()
        except (User.DoesNotExist, KeyError, ValueError):
            logger.warning("WS recusado: usuário do token não existe ou está inativo.")

            return AnonymousUser()

    @staticmethod
    def _get_token(scope):
        query_string = scope.get("query_string", b"").decode()
        token = parse_qs(query_string).get("token")

        return token[0] if token else None


def JWTAuthMiddlewareStack(inner):
    return JWTAuthMiddleware(inner)
