import os
import json
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api.event.filter import event_message # 必须有这个，才能监听群聊 @

@register("astrbot_plugin_mention_reply", "qingcai", "群友专属回复助手", "1.3.5")
class MentionReplyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 配置文件路径
        self.db_path = os.path.join("data", "mention_reply_config.json")
        self.config = self._load_config()

    def _load_config(self):
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return {"enabled": True, "admin_qq": ["1023902556"], "replies": {}}
        return {"enabled": True, "admin_qq": ["1023902556"], "replies": {}}

    def _save_config(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=4)

    # --- 核心功能：监听所有消息 ---
    @event_message
    async def on_message_handler(self, event: AstrMessageEvent):
        if not self.config.get("enabled", True): return
        
        # 获取消息链
        msg_chain = event.get_messages()
        
        # 遍历消息，看看有没有 @ 信息
        for seg in msg_chain:
            # 在 AstrBot 中，At 对象的 type 通常是 "at"
            if seg.type == "at":
                # 拿到被 @ 人的 QQ 号
                target_id = str(seg.data.get("qq") or seg.data.get("user_id", ""))
                
                # 如果这个 QQ 号在我们的回复名单里
                if target_id in self.config.get("replies", {}):
                    reply_text = self.config["replies"][target_id]
                    # 发送回复
                    await event.send_message([reply_text])
                    # 停止后续处理，不让大模型说话
                    event.stop_event()
                    return

    # --- 指令：帮助菜单 ---
    @filter.command("嘴替帮助")
    async def help_cmd(self, event: AstrMessageEvent):
        help_text = (
            "🤖 **嘴替助手指令**\n"
            "1. `/setreply @用户 内容` - 设置代答\n"
            "2. `/delreply @用户` - 删除代答\n"
            "3. `/listreply` - 查看列表"
        )
        yield event.plain_result(help_text)

    # --- 指令：设置回复 ---
    @filter.command("setreply")
    async def set_reply(self, event: AstrMessageEvent, *, content: str):
        # 权限校验：只允许 admin_qq 里的用户操作
        sender_id = str(event.get_sender_id())
        if sender_id not in self.config.get("admin_qq", []):
            yield event.plain_result("❌ 权限不足。")
            return

        # 手动解析消息里的 @ 信息
        target_id = ""
        msg_chain = event.get_messages()
        for seg in msg_chain:
            if seg.type == "at":
                target_id = str(seg.data.get("qq") or seg.data.get("user_id", ""))
                break
        
        if not target_id:
            yield event.plain_result("❌ 格式错误：请 /setreply @某人 回复内容")
            return

        # 清理内容，去掉 @ 文本部分（如果有的话）
        # content 已经是去掉指令后的部分了，我们只需要保存回复语
        self.config["replies"][target_id] = content.strip()
        self._save_config()
        yield event.plain_result(f"✅ 已设置，当有人 @{target_id} 时，我会回复：\n{content.strip()}")

    # --- 指令：删除回复 ---
    @filter.command("delreply")
    async def del_reply(self, event: AstrMessageEvent):
        sender_id = str(event.get_sender_id())
        if sender_id not in self.config.get("admin_qq", []): return

        target_id = ""
        for seg in event.get_messages():
            if seg.type == "at":
                target_id = str(seg.data.get("qq") or seg.data.get("user_id", ""))
                break
        
        if target_id in self.config.get("replies", {}):
            del self.config["replies"][target_id]
            self._save_config()
            yield event.plain_result(f"✅ 已删除 {target_id} 的设置")
        else:
            yield event.plain_result("❌ 该用户没设置过。")

    # --- 指令：查看列表 ---
    @filter.command("listreply")
    async def list_reply(self, event: AstrMessageEvent):
        replies = self.config.get("replies", {})
        if not replies:
            yield event.plain_result("📭 嘴替列表为空。")
            return
        
        res = "📋 当前嘴替列表:\n"
        for q, t in replies.items():
            res += f"QQ:{q} -> {t}\n"
        yield event.plain_result(res)
