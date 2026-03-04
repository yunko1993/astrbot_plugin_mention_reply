import os
import json
import asyncio
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
            # 初始化默认配置
            default_config = {"enabled": True, "admin_qq": [], "replies": {}}
            self.save_config(default_config)
            return default_config

    def save_config(self, config):
        """保存配置文件"""
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    # --- 核心功能：监听群消息 ---
    async def on_message(self, event: AstrMessageEvent):
        # 只处理群消息
        if event.get_message_type() != MessageType.GROUP_MESSAGE:
            return

        # 检查全局开关
        if not self.config.get("enabled", True):
            return

        message_chain = event.get_messages()
        sender_id = str(event.get_sender_id())
        
        # 遍历消息链，查找 @ 自己的消息
        for seg in message_chain:
            if seg.type == "at":
                # 兼容不同平台的字段名 (NapCat/OneBot 通常是 user_id 或 qq)
                at_id = str(seg.data.get("qq") or seg.data.get("user_id") or "")
                bot_id = str(event.get_self_id())
                
                if at_id == bot_id:
                    # 找到了 @ 自己，检查是否有预设回复
                    if sender_id in self.config.get("replies", {}):
                        reply_text = self.config["replies"][sender_id]
                        await event.send(reply_text)
                        return # 回复后不再处理其他逻辑

    # --- 命令：设置回复 ---
    # 新版写法：直接使用 context.register_command 或者在类方法上加装饰器
    # 这里采用最通用的新方法：直接在方法上定义指令
    async def cmd_setreply(self, event: AstrMessageEvent, target_user, *, content: str):
        """设置回复内容 /setreply @用户 内容"""
        if event.get_sender_id() not in self.config.get("admin_qq", []):
            yield event.plain_result("❌ 权限不足，只有管理员可以设置。")
            return

        if not content:
            yield event.plain_result("❌ 格式错误：/setreply @用户 回复内容")
            return

        user_id = str(target_user.id) # 获取被 @ 用户的 ID
        self.config.setdefault("replies", {})
        self.config["replies"][user_id] = content
        self.save_config(self.config)
        
        yield event.plain_result(f"✅ 已设置：当有人 @{target_user.nickname} 时，自动回复：\n{content}")

    # 注册命令 (新版标准写法)
    # 注意：AstrBot v4+ 通常会自动扫描带有特定参数的方法来注册命令
    # 如果上述 cmd_ 前缀不生效，可能需要用 ctx.register_command
    # 但为了简化，我们尝试用最简单的指令解析方式，或者手动注册
    
    # 【重要修正】针对 v4.16+ 的最佳实践：
    # 很多新版插件直接在 on_message 里解析命令，或者使用新的 router
    # 为了保证 100% 兼容且不依赖复杂的 router 配置，我们把命令逻辑也放进 on_message 里统一处理
    # 这样最稳，不会报 AttributeError
    
    async def on_message_extended(self, event: AstrMessageEvent):
        """扩展消息处理，包含命令解析"""
        # 先运行原有的 @ 回复逻辑
        await self.on_message(event)
        
        # 如果是私聊或者非群聊，也可以处理命令，这里主要演示群命令
        msg_str = event.get_message_str().strip()
        if not msg_str.startswith("/"):
            return

        parts = msg_str.split(maxsplit=2) # 分割命令
        cmd = parts[0]
        
        # 1. 帮助命令
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

        # 2. 设置回复命令
        if cmd == "/setreply":
            if event.get_sender_id() not in self.config.get("admin_qq", []):
                await event.send("❌ 权限不足，只有管理员可以设置。")
                return
            
            if len(parts) < 3:
                await event.send("❌ 格式错误：/setreply @用户 回复内容")
                return
            
            # 解析 @ 用户
            message_chain = event.get_messages()
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

            content = parts[2] # 剩下的全是内容
            self.config.setdefault("replies", {})
            self.config["replies"][target_user["id"]] = content
            self.save_config(self.config)
            
            await event.send(f"✅ 已设置：当有人 @{target_user['nickname']} 时，自动回复：\n{content}")
            return

        # 3. 删除回复命令
        if cmd == "/delreply":
            if event.get_sender_id() not in self.config.get("admin_qq", []):
                await event.send("❌ 权限不足。")
                return

            message_chain = event.get_messages()
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

        # 4. 列表命令
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
                # 尝试获取昵称 (简化处理，实际可能需要缓存或查询)
                text += f"- 用户ID: {uid}\n  回复: {content[:20]}...\n"
            await event.send(text)
            return

        # 5. 开关命令
        if cmd == "/toggle":
            if event.get_sender_id() not in self.config.get("admin_qq", []):
                await event.send("❌ 权限不足。")
                return
            
            self.config["enabled"] = not self.config.get("enabled", True)
            self.save_config(self.config)
            status = "✅ 已开启" if self.config["enabled"] else "⏸️ 已暂停"
            await event.send(f"{status} 群友专属回复功能。")
            return

    # 绑定消息事件
    # 在新版 AstrBot 中，通常需要显式绑定事件处理器
    # 如果你的 main.py 是作为 Star 加载的，on_message 会被自动调用
    # 但为了确保命令也能被捕获，我们重载 on_message
    async def on_message(self, event: AstrMessageEvent):
        # 合并原来的逻辑和命令逻辑
        await self.on_message_extended(event)
