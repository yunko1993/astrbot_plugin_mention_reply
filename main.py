import json
import os
import logging
from astrbot.api.event import filter
from astrbot.api.star import Context, Star, register
from astrbot.core.platform import AstrMessageEvent
from astrbot.api.event.filter import event_message

logger = logging.getLogger("astrbot")

@register("astrbot_plugin_mention_reply", "qingcai", "群友专属回复助手", "1.4.6")
class MentionReplyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.db_path = os.path.join("data", "mention_reply_config.json")
        self.config = self._load_config()

    def _load_config(self):
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except: pass
        return {"enabled": True, "admin_qq": ["1023902556"], "replies": {}}

    def _save_config(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=4)

    @event_message
    async def handle_mentions(self, event: AstrMessageEvent):
        if not self.config.get("enabled", True): return
        if event.message_str.startswith("/"): return

        for seg in event.get_messages():
            t_id = ""
            if hasattr(seg, 'type') and seg.type == "at":
                t_id = str(seg.data.get("qq") or seg.data.get("user_id", ""))
            elif hasattr(seg, 'qq') and seg.qq:
                t_id = str(seg.qq)
            
            if t_id and t_id in self.config.get("replies", {}):
                event.stop_event()
                yield event.plain_result(self.config["replies"][t_id])
                return

    @filter.command("嘴替帮助")
    async def help_cmd(self, event: AstrMessageEvent):
        yield event.plain_result("🤖 嘴替助手\n1. /setreply @某人 内容\n2. /delreply @某人\n3. /listreply\n4. /toggle")

    @filter.command("setreply")
    async def set_reply(self, event: AstrMessageEvent, *, content: str = ""):
        if str(event.get_sender_id()) not in self.config.get("admin_qq", []): return
        target_id = ""
        for seg in event.get_messages():
            if (hasattr(seg, 'type') and seg.type == "at") or (hasattr(seg, 'qq') and seg.qq):
                target_id = str(getattr(seg, 'qq', seg.data.get("qq") if hasattr(seg, 'data') else ""))
                break
        if not target_id:
            yield event.plain_result("⚠️ 请 @ 一个用户")
            return
        self.config["replies"][target_id] = content.strip()
        self._save_config()
        yield event.plain_result(f"✅ 已设置 QQ:{target_id} 的嘴替")

    @filter.command("delreply")
    async def del_reply(self, event: AstrMessageEvent):
        if str(event.get_sender_id()) not in self.config.get("admin_qq", []): return
        target_id = ""
        for seg in event.get_messages():
            if (hasattr(seg, 'type') and seg.type == "at") or (hasattr(seg, 'qq') and seg.qq):
                target_id = str(getattr(seg, 'qq', seg.data.get("qq") if hasattr(seg, 'data') else ""))
                break
        if target_id in self.config["replies"]:
            del self.config["replies"][target_id]
            self._save_config()
            yield event.plain_result("✅ 已删除")

    @filter.command("listreply")
    async def list_reply(self, event: AstrMessageEvent):
        yield event.plain_result(f"嘴替列表: {self.config['replies']}")

    @filter.command("toggle")
    async def toggle_cmd(self, event: AstrMessageEvent):
        self.config["enabled"] = not self.config.get("enabled", True)
        self._save_config()
        yield event.plain_result(f"已{'开启' if self.config['enabled'] else '关闭'}")
