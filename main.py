import os
import json
from astrbot.api import star, logger
from astrbot.api.event import AstrMessageEvent, MessageEventResult
from astrbot.api.platform import MessageType
from astrbot.api.star import Context

# 配置路径
DATA_PATH = "data/plugins/astrbot_plugin_mention_reply/"
CONFIG_FILE = DATA_PATH + "config.json"

# 确保目录存在
if not os.path.exists(DATA_PATH):
    os.makedirs(DATA_PATH)

@star.register(name="astrbot_plugin_mention_reply", desc="群友专属回复助手", author="qingcai", version="1.2.1")
class Main(star.Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.config = self.load_config()

    def load_config(self):
        """加载配置文件"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                logger.error("配置文件读取失败，使用默认配置")
                return {"enabled": True, "admin_qq": [], "replies": {}}
        else:
            default_config = {"enabled": True, "admin_qq": [], "replies": {}}
            self.save_config(default_config)
            return default_config

    def save_config(self, config):
        """保存配置文件"""
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    async def on_message(self, event: AstrMessageEvent):
        # 只处理群消息
        if event.get_message_type() != MessageType.GROUP_MESSAGE:
            return

        # 检查全局开关
        if not self.config.get("enabled", True):
            return

        message_chain = event.get_messages()
        sender_id = str(event.get_sender_id())
        msg_str = event.get_message_str().strip()

        # --- 1. 处理命令 ---
        if msg_str.startswith("/"):
            parts = msg_str.split(maxsplit=2)
            cmd = parts[0]

            # 帮助命令
            if cmd in ["/嘴替帮助", "/reply_help"]:
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
                await event.send(help_text)
                return

            # 设置回复命令
            if cmd == "/setreply":
                if event.get_sender_id() not in self.config.get("admin_qq", []):
                    await event.send("❌ 权限不足，只有管理员可以设置。")
                    return
                
                if len(parts) < 3:
                    await event.send("❌ 格式错误：/setreply @用户 回复内容")
                    return
                
                # 解析 @ 用户
                target_user = None
                for seg in message_chain:
                    if seg.type == "at":
                        uid = seg.data.get("qq") or seg.data.get("user_id")
                        if uid:
                            target_user = {"id": str(uid), "nickname": seg.data.get("nickname", "未知")}
                            break
                
                if not target_user:
                    await event.send("❌ 未找到有效的 @ 用户，请确保格式为：/setreply @用户 内容")
                    return

                content = parts[2]
                self.config.setdefault("replies", {})
                self.config["replies"][target_user["id"]] = content
                self.save_config(self.config)
                
                await event.send(f"✅ 已设置：当有人 @{target_user['nickname']} 时，自动回复：\n{content}")
                return

            # 删除回复命令
            if cmd == "/delreply":
                if event.get_sender_id() not in self.config.get("admin_qq", []):
                    await event.send("❌ 权限不足。")
                    return

                target_id = None
                for seg in message_chain:
                    if seg.type == "at":
                        target_id = str(seg.data.get("qq") or seg.data.get("user_id"))
                        break
                
                if not target_id or target_id not in self.config.get("replies", {}):
                    await event.send("❌ 该用户没有设置回复，或格式错误。")
                    return

                del self.config["replies"][target_id]
                self.save_config(self.config)
                await event.send("✅ 已删除该用户的自动回复。")
                return

            # 列表命令
            if cmd == "/listreply":
                if event.get_sender_id() not in self.config.get("admin_qq", []):
                    await event.send("❌ 权限不足。")
                    return
                
                replies = self.config.get("replies", {})
                if not replies:
                    await event.send("📭 当前没有任何设置的回复。")
                    return
                
                text = "📋 **当前回复列表**:\n"
                for uid, content in replies.items():
                    text += f"- 用户ID: {uid}\n  回复: {content[:20]}...\n"
                await event.send(text)
                return

            # 开关命令
            if cmd == "/toggle":
                if event.get_sender_id() not in self.config.get("admin_qq", []):
                    await event.send("❌ 权限不足。")
                    return
                
                self.config["enabled"] = not self.config.get("enabled", True)
                self.save_config(self.config)
                status = "✅ 已开启" if self.config["enabled"] else "⏸️ 已暂停"
                await event.send(f"{status} 群友专属回复功能。")
                return

            # 未知命令
            await event.send(f"❓ 未知命令：{cmd}，输入 /嘴替帮助 查看使用说明。")
            return

        # --- 2. 处理 @ 回复逻辑 ---
        # 遍历消息链，查找 @ 自己的消息
        for seg in message_chain:
            if seg.type == "at":
                at_id = str(seg.data.get("qq") or seg.data.get("user_id") or "")
                bot_id = str(event.get_self_id())
                
                if at_id == bot_id:
                    # 找到了 @ 自己，检查是否有预设回复
                    if sender_id in self.config.get("replies", {}):
                        reply_text = self.config["replies"][sender_id]
                        await event.send(reply_text)
                        return  # 回复后不再处理其他逻辑
