import os
import json
import astrbot.api.star as star
from astrbot.api.event import AstrMessageEvent
from astrbot.api.platform import MessageType
from astrbot.api import sp

# 配置文件路径
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "replies.json")
# 开关状态文件路径
STATUS_PATH = os.path.join(os.path.dirname(__file__), "status.json")

@star.register(name="astrbot_plugin_mention_reply", desc="群友专属回复助手", author="qingcai", version="1.2.1")
class Main(star.Star):
    def __init__(self, context: star.Context) -> None:
        self.context = context
        self.replies = self._load_replies()
        self.status = self._load_status()

    def _load_replies(self):
        if not os.path.exists(CONFIG_PATH):
            return {}
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}

    def _save_replies(self):
        try:
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(self.replies, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"[ MentionReply ] 保存配置失败: {e}")

    def _load_status(self):
        if not os.path.exists(STATUS_PATH):
            return {"enabled": True}
        try:
            with open(STATUS_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {"enabled": True}

    def _save_status(self):
        try:
            with open(STATUS_PATH, 'w', encoding='utf-8') as f:
                json.dump(self.status, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"[ MentionReply ] 保存状态失败: {e}")

    async def _get_nickname(self, uid: str, platform: str):
        try:
            info = await self.context.get_user_info(uid, platform)
            return info.get("nickname", f"用户{uid}") if info else f"用户{uid}"
        except:
            return f"用户{uid}"

    async def _is_admin(self, event: AstrMessageEvent):
        role = event.get_role()
        return role in ["owner", "admin"]

    @sp.command("/reply_help")
    @sp.command("/嘴替帮助")
    async def cmd_help(self, event: AstrMessageEvent):
        """显示本插件的帮助信息"""
        help_text = (
            "🎭 **群友专属回复助手 - 使用指南**\n\n"
            "🔹 **设置台词**\n"
            "`/setreply @某人 台词内容`\n"
            "例：`/setreply @老王 我在搬砖，勿扰`\n"
            "*(只能设置自己的，管理员可设置任何人)*\n\n"
            "🔹 **删除台词**\n"
            "`/delreply @某人`\n"
            "*(删除某人的自动回复配置)*\n\n"
            "🔹 **查看列表**\n"
            "`/listreply`\n"
            "*(查看谁设置了台词)*\n\n"
            "🔹 **功能开关** (仅管理员)\n"
            "`/switch_mention`\n"
            "*(开启/关闭自动回复功能)*\n\n"
            "💡 **怎么玩？**\n"
            "只要有人在群里 **@你**，机器人就会自动替你说出你设置的台词！\n"
            "快去设置一句骚话吧～"
        )
        await event.send(help_text)

    @sp.command("/setreply")
    async def cmd_set_reply(self, event: AstrMessageEvent, message: str = ""):
        """设置专属回复"""
        if event.get_message_type() != MessageType.GROUP_MESSAGE:
            await event.send("❌ 此功能仅限群聊使用。")
            return

        target_uid = None
        for seg in event.message.message:
            if seg.type == "mention":
                target_uid = str(seg.data.get("qq") or seg.data.get("user_id"))
                break
        
        if not target_uid:
            await event.send("❌ 格式错误！请 @ 想要设置的群友。\n输入 `/嘴替帮助` 查看用法。")
            return

        text_parts = []
        for seg in event.message.message:
            if seg.type == "text":
                text_parts.append(seg.data.get("text", "").strip())
        
        content = " ".join(text_parts).strip()
        if not content and message:
            content = message.strip()

        if not content:
            await event.send("❌ 请输入要设置的回复内容。\n例：`/setreply @自己 我很忙`\n输入 `/嘴替帮助` 查看更多。")
            return

        sender_id = str(event.get_sender_id())
        is_admin = await self._is_admin(event)

        if sender_id != target_uid and not is_admin:
            await event.send("❌ 你没有权限修改别人的台词哦！")
            return

        self.replies[target_uid] = content
        self._save_replies()

        nickname = await self._get_nickname(target_uid, event.get_platform_name())
        await event.send(f"✅ 已设置 [{nickname}] 的专属回复：\n「{content}」")

    @sp.command("/delreply")
    async def cmd_del_reply(self, event: AstrMessageEvent):
        """删除专属回复"""
        if event.get_message_type() != MessageType.GROUP_MESSAGE:
            return

        target_uid = None
        for seg in event.message.message:
            if seg.type == "mention":
                target_uid = str(seg.data.get("qq") or seg.data.get("user_id"))
                break
        
        if not target_uid:
            await event.send("❌ 请 @ 要删除配置的群友。\n输入 `/嘴替帮助` 查看用法。")
            return

        sender_id = str(event.get_sender_id())
        is_admin = await self._is_admin(event)

        if sender_id != target_uid and not is_admin:
            await event.send("❌ 你没有权限删除别人的配置。")
            return

        if target_uid in self.replies:
            nickname = await self._get_nickname(target_uid, event.get_platform_name())
            del self.replies[target_uid]
            self._save_replies()
            await event.send(f"🗑️ 已清除 [{nickname}] 的专属回复。")
        else:
            await event.send("ℹ️ 该群友本来就没有设置回复。")

    @sp.command("/switch_mention")
    async def cmd_switch(self, event: AstrMessageEvent):
        """开关插件功能"""
        if event.get_message_type() != MessageType.GROUP_MESSAGE:
            return
        
        if not await self._is_admin(event):
            await event.send("❌ 只有群主或管理员才能开关此功能。")
            return

        self.status["enabled"] = not self.status["enabled"]
        self._save_status()
        
        status_text = "🟢 已开启" if self.status["enabled"] else "🔴 已关闭"
        await event.send(f"💡 群友专属回复功能 {status_text}。")

    @sp.command("/listreply")
    async def cmd_list_reply(self, event: AstrMessageEvent):
        """列出所有已设置的回复"""
        if not self.replies:
            await event.send("📭 目前还没有人设置专属回复哦。\n输入 `/嘴替帮助` 查看如何设置。")
            return
        
        msg = "📋 **当前已设置的专属回复：**\n\n"
        for uid, text in self.replies.items():
            nickname = await self._get_nickname(uid, event.get_platform_name())
            display_text = text[:20] + "..." if len(text) > 20 else text
            msg += f"👤 {nickname}: {display_text}\n"
        
        await event.send(msg)

    async def on_message(self, event: AstrMessageEvent):
        """监听消息：只要有人 @别人，就检查是否有台词"""
        if event.get_message_type() != MessageType.GROUP_MESSAGE:
            return

        if not self.status.get("enabled", True):
            return

        targets = []
        for seg in event.message.message:
            if seg.type == "mention":
                uid = str(seg.data.get("qq") or seg.data.get("user_id"))
                targets.append(uid)
        
        if not targets:
            return

        active_replies = []
        for uid in targets:
            if uid in self.replies:
                nickname = await self._get_nickname(uid, event.get_platform_name())
                content = self.replies[uid]
                active_replies.append(f"🎭 **{nickname}** 说：\n{content}")
        
        if active_replies:
            final_msg = "\n------------------\n".join(active_replies)
            await event.send(final_msg)