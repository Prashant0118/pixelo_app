import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import User

from myapp.models import Message


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close()
            return

        self.user = user
        self.peer_username = self.scope["url_route"]["kwargs"]["username"]
        self.peer = await self._get_user_by_username(self.peer_username)

        if not self.peer or self.peer.id == self.user.id:
            await self.close()
            return

        low_id, high_id = sorted([self.user.id, self.peer.id])
        self.room_group_name = f"chat_{low_id}_{high_id}"

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        seen_ids = await self._mark_seen_messages(sender_id=self.peer.id, receiver_id=self.user.id)
        if seen_ids:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "seen_update",
                    "message_ids": seen_ids,
                },
            )

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return

        try:
            payload = json.loads(text_data)
        except json.JSONDecodeError:
            return

        message_text = (payload.get("message") or "").strip()
        if not message_text:
            return

        message = await self._create_message(
            sender_id=self.user.id,
            receiver_id=self.peer.id,
            content=message_text,
        )

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message": {
                    "id": message.id,
                    "content": message.content,
                    "sender": self.user.username,
                    "sender_id": self.user.id,
                    "is_seen": message.is_seen,
                    "timestamp": message.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                },
            },
        )

    async def chat_message(self, event):
        message = event["message"]
        message["is_mine"] = message.get("sender_id") == self.user.id
        await self.send(text_data=json.dumps({"message": message}))

    async def seen_update(self, event):
        await self.send(text_data=json.dumps({
            "type": "seen_update",
            "message_ids": event.get("message_ids", []),
        }))

    @database_sync_to_async
    def _get_user_by_username(self, username):
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist:
            return None

    @database_sync_to_async
    def _create_message(self, sender_id, receiver_id, content):
        return Message.objects.create(
            sender_id=sender_id,
            receiver_id=receiver_id,
            content=content,
        )

    @database_sync_to_async
    def _mark_seen_messages(self, sender_id, receiver_id):
        qs = Message.objects.filter(
            sender_id=sender_id,
            receiver_id=receiver_id,
            is_seen=False
        )
        ids = list(qs.values_list("id", flat=True))
        if ids:
            qs.update(is_seen=True)
        return ids
