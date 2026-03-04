import os
import json
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api.platform import MessageType

@register("astrbot_plugin_mention_reply", "qingcai", "群友专属回复助手", "1.3.0")
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
                return {"enabled": True, "admin_qq": [], "replies": {}}
        return {"enabled": True, "admin_qq": [], "replies": {}}

    def _save_config(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=4)

    # --- 核心功能：监听群消息并回复 ---
    async def on_message(self, event: AstrMessageEvent):
        # 1. 只处理群消息
        if event.get_message_type() != MessageType.GROUP_MESSAGE:
            return
        
        # 2. 检查全局开关
        if not self.config.get("enabled", True):
            return

        message_chain = event.get_messages()
        sender_id = str(event.get_sender_id())
        bot_id = str(event.get_self_id())

        # 3. 遍历消息，检查是否 @ 了机器人
        for seg in message_chain:
            if seg.type == "at":
                at_id = str(seg.data.get("qq") or seg.data.get("user_id") or "")
                
                # 如果 @ 的是机器人自己
                if at_id == bot_id:
                    # 检查该发送者是否有预设回复
                    if sender_id in self.config.get("replies", {}):
                        reply_text = self.config["replies"][sender_id]
                        await event.send(reply_text)
                        return # 回复后结束，避免重复处理

    # --- 指令：帮助菜单 ---
    @filter.command("嘴替帮助")
    async def help_cmd(self, event: AstrMessageEvent):
        help_text = (
            "🤖 **群友专属回复助手**\n\n"
            "📜 **指令列表**:\n"
            "1. `/setreply @用户 内容` - 设置指定用户的自动回复 (仅管理员)\n"
            "2. `/delreply @用户` - 删除指定用户的自动回复 (仅管理员)\n"
            "3. `/listreply` - 查看所有已设置的回复 (仅管理员)\n"
            "4. `/toggle` - 开启/关闭插件全局开关 (仅管理员)\n"
            "5. `/嘴替帮助` - 显示本帮助信息\n\n"
            "💡 **示例**:\n"
            "`/setreply @张三 哈哈，你说得对！`\n"
            "当群里有人 @张三 时，机器人就会说：哈哈，你说得对！"
        )
        yield event.plain_result(help_text)

    # --- 指令：设置回复 ---
    @filter.command("setreply")
    async def set_reply(self, event: AstrMessageEvent, target_user, *, content: str):
        # 权限检查
        if event.get_sender_id() not in self.config.get("admin_qq", []):
            yield event.plain_result("❌ 权限不足，只有管理员可以设置。")
            return

        if not content:
            yield event.plain_result("❌ 格式错误：/setreply @用户 回复内容")
            return

        # 获取被 @ 用户的 ID (target_user 是框架自动解析的对象)
        # 注意：不同版本框架 target_user 可能是对象也可能是字符串，这里做兼容
        user_id = ""
        user_nick = "未知"
        
        if hasattr(target_user, 'id'):
            user_id = str(target_user.id)
            user_nick = getattr(target_user, 'nickname', '未知')
        else:
            # 如果框架没自动解析，尝试从原始消息链找 (备用方案)
            # 通常 @filter.command 带参数会自动解析 @
            pass

        if not user_id:
             yield event.plain_result("❌ 未识别到用户，请确保格式为：/setreply @用户 内容")
             return

        self.config.setdefault("replies", {})
        self.config["replies"][user_id] = content
        self._save_config()
        
        yield event.plain_result(f"✅ 已设置：当有人 @{user_nick} 时，自动回复：\n{content}")

    # --- 指令：删除回复 ---
    @filter.command("delreply")
    async def del_reply(self, event: AstrMessageEvent, target_user):
        if event.get_sender_id() not in self.config.get("admin_qq", []):
            yield event.plain_result("❌ 权限不足。")
            return

        user_id = ""
        if hasattr(target_user, 'id'):
            user_id = str(target_user.id)
        
        if not user_id or user_id not in self.config.get("replies", {}):
            yield event.plain_result("❌ 该用户没有设置回复，或格式错误。")
            return

        del self.config["replies"][user_id]
        self._save_config()
        yield event.plain_result("✅ 已删除该用户的自动回复。")

    # --- 指令：查看列表 ---
    @filter.command("listreply")
    async def list_reply(self, event: AstrMessageEvent):
        if event.get_sender_id() not in self.config.get("admin_qq", []):
            yield event.plain_result("❌ 权限不足。")
            return
        
        replies = self.config.get("replies", {})
        if not replies:
            yield event.plain_result("📭 当前没有任何设置的回复。")
            return
        
        text = "📋 **当前回复列表**:\n"
        for uid, content in replies.items():
            text += f"- ID: {uid}\n  回复: {content[:20]}...\n"
        yield event.plain_result(text)

    # --- 指令：开关插件 ---
    @filter.command("toggle")
    async def toggle_plugin(self, event: AstrMessageEvent):
        if event.get_sender_id() not in self.config.get("admin_qq", []):
            yield event.plain_result("❌ 权限不足。")
            return
        
        self.config["enabled"] = not self.config.get("enabled", True)
        self._save_config()
        status = "✅ 已开启" if self.config["enabled"] else "⏸️ 已暂停"
        yield event.plain_result(f"{status} 群友专属回复功能。")
