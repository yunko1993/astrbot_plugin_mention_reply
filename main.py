import json
import os
import logging
from astrbot.api.event import filter
from astrbot.api.star import Context, Star, register
from astrbot.core.platform import AstrMessageEvent
# 修正导包路径：从 api.event 导入，如果还不行就用 handle_event 兜底
try:
    from astrbot.api.event import on_message as event_message
except ImportError:
    try:
        from astrbot.api.event.filter import event_message
    except ImportError:
        # 如果都找不到，定义一个空装饰器防止崩溃
        def event_message(func): return func

logger = logging.getLogger("astrbot")

@register("astrbot_plugin_mention_reply", "qingcai", "群友专属回复助手", "1.4.7")
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

    # --- 核心功能：监听被 @ 的消息 ---
    @event_message
    async def handle_mentions(self, event: AstrMessageEvent):
        if not self.config.get("enabled", True): return
        if event.message_str.startswith("/"): return

        chain = event.get_messages()
        for seg in chain:
            # 这里的解析针对 NapCat/OneBot11 做了多重兼容
            t_id = ""
            if hasattr(seg, 'type') and seg.type == "at":
                t_id = str(seg.data.get("qq") or seg.data.get("user_id", ""))
            elif hasattr(seg, 'qq') and seg.qq:
                t_id = str(seg.qq)
            
            if t_id and t_id in self.config.get("replies", {}):
                event.stop_event()
                yield event.plain_result(self.config["replies"][t_id])
                return

    # --- 指令：帮助菜单 ---
    @filter.command("嘴替帮助")
    async def help_cmd(self, event: AstrMessageEvent):
        status = "🟢 运行中" if self.config.get("enabled", True) else "🔴 已关闭"
        help_text = (
            f"🤖 **群友嘴替助手 ({status})**\n"
            "--------------------------\n"
            "1. `/setreply @用户 内容` - 设置代答\n"
            "2. `/delreply @用户` - 删除设置\n"
            "3. `/listreply` - 查看列表\n"
            "4. `/toggle` - 插件总开关\n"
            "--------------------------"
        )
        yield event.plain_result(help_text)

    # --- 指令：设置代答 ---
    @filter.command("setreply")
    async def set_reply(self, event: AstrMessageEvent, *, content: str = ""):
        if str(event.get_sender_id()) not in self.config.get("admin_qq", []):
            yield event.plain_result("❌ 你不是管理员")
            return

        target_id = ""
        for seg in event.get_messages():
            if (hasattr(seg, 'type') and seg.type == "at") or (hasattr(seg, 'qq') and seg.qq):
                # 针对不同版本框架解析 QQ 号
                target_id = str(getattr(seg, 'qq', seg.data.get("qq") if hasattr(seg, 'data') else ""))
                if target_id: break
        
        if not target_id:
            yield event.plain_result("⚠️ 识别失败！请在指令中 @ 一个用户。")
            return

        # 去掉内容首尾空格
        self.config["replies"][target_id] = content.strip()
        self._save_config()
        yield event.plain_result(f"✅ 设置成功！有人 @{target_id} 时，我会回复：\n{content.strip()}")

    # --- 指令：删除代答 ---
    @filter.command("delreply")
    async def del_reply(self, event: AstrMessageEvent):
        if str(event.get_sender_id()) not in self.config.get("admin_qq", []): return

        target_id = ""
        for seg in event.get_messages():
            if (hasattr(seg, 'type') and seg.type == "at") or (hasattr(seg, 'qq') and seg.qq):
                target_id = str(getattr(seg, 'qq', seg.data.get("qq") if hasattr(seg, 'data') else ""))
                if target_id: break
        
        if target_id in self.config.get("replies", {}):
            del self.config["replies"][target_id]
            self._save_config()
            yield event.plain_result(f"✅ 已删除针对 {target_id} 的设置。")
        else:
            yield event.plain_result("❌ 该用户目前没有设置代答。")

    # --- 指令：查看列表 ---
    @filter.command("listreply")
    async def list_reply(self, event: AstrMessageEvent):
        replies = self.config.get("replies", {})
        if not replies:
            yield event.plain_result("📭 列表空空如也。")
            return
        res = "📋 当前代答列表:\n" + "\n".join([f"• {k}: {v}" for k, v in replies.items()])
        yield event.plain_result(res)

    # --- 指令：开关 ---
    @filter.command("toggle")
    async def toggle_cmd(self, event: AstrMessageEvent):
        if str(event.get_sender_id()) not in self.config.get("admin_qq", []): return
        self.config["enabled"] = not self.config.get("enabled", True)
        self._save_config()
        yield event.plain_result(f"✅ 嘴替功能已{'开启' if self.config['enabled'] else '关闭'}。")
