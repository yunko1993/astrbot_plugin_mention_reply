import os
import json
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api.event.filter import event_message # 必须导入这个
from astrbot.api.message_components import At # 导入 At 组件

@register("astrbot_plugin_mention_reply", "qingcai", "群友专属回复助手", "1.3.0")
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
            except:
                pass
        return {"enabled": True, "admin_qq": ["1023902556"], "replies": {}} # 默认把你加入管理员

    def _save_config(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=4)

    # --- 核心功能：监听群消息中是否有人被 @ ---
    @event_message
    async def handle_mentions(self, event: AstrMessageEvent):
        if not self.config.get("enabled", True): return
        
        message_chain = event.get_messages()
        
        # 遍历消息段，寻找 At 信息
        for seg in message_chain:
            if isinstance(seg, At):
                target_id = str(seg.qq)
                # 如果被 @ 的人在我们的“嘴替”名单里
                if target_id in self.config.get("replies", {}):
                    reply_text = self.config["replies"][target_id]
                    # 发送回复
                    await event.send_message([reply_text])
                    # 停止后续处理（防止指令被大模型再次响应）
                    event.stop_event() 

    # --- 指令：帮助菜单 (增加了 alias 兼容你的习惯) ---
    @filter.command("嘴替帮助")
    @filter.alias("reply_help") # 这样你打 /reply_help 也能触发
    async def help_cmd(self, event: AstrMessageEvent):
        help_text = (
            "🤖 **群友专属回复助手**\n"
            "1. `/setreply @用户 内容` - 设置代答\n"
            "2. `/delreply @用户` - 删除代答\n"
            "3. `/listreply` - 查看列表\n"
            "4. `/toggle` - 开关插件\n"
            "5. `/add_admin QQ号` - 添加管理员"
        )
        yield event.plain_result(help_text)

    # --- 指令：设置回复 ---
    @filter.command("setreply")
    async def set_reply(self, event: AstrMessageEvent, target_user: At, *, content: str):
        # 权限检查：检查是否在管理员名单，或者是框架定义的超级管理员
        sender_id = str(event.get_sender_id())
        if sender_id not in self.config.get("admin_qq", []) and not event.is_admin:
            yield event.plain_result("❌ 你没有管理权限。")
            return

        user_id = str(target_user.qq)
        self.config.setdefault("replies", {})
        self.config["replies"][user_id] = content
        self._save_config()
        
        yield event.plain_result(f"✅ 已设置：当有人 @{user_id} 时，我会代答：\n{content}")

    # --- 指令：删除回复 ---
    @filter.command("delreply")
    async def del_reply(self, event: AstrMessageEvent, target_user: At):
        if str(event.get_sender_id()) not in self.config.get("admin_qq", []) and not event.is_admin:
            yield event.plain_result("❌ 权限不足。")
            return

        user_id = str(target_user.qq)
        if user_id in self.config.get("replies", {}):
            del self.config["replies"][user_id]
            self._save_config()
            yield event.plain_result(f"✅ 已删除针对 {user_id} 的自动回复。")
        else:
            yield event.plain_result("❌ 该用户未设置代答。")

    # --- 辅助指令：添加管理员 ---
    @filter.command("add_admin")
    async def add_admin(self, event: AstrMessageEvent, qq: str):
        if not event.is_admin and str(event.get_sender_id()) not in self.config["admin_qq"]:
            return
        if qq not in self.config["admin_qq"]:
            self.config["admin_qq"].append(qq)
            self._save_config()
            yield event.plain_result(f"✅ 已添加管理员: {qq}")
