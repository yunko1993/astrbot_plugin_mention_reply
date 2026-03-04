import json
import os
import logging
from astrbot.api.event import filter
from astrbot.api.star import Context, Star, register
from astrbot.core.platform import AstrMessageEvent

# 针对 v4.16.0 的兼容性导包
try:
    from astrbot.api.event import on_message as event_message
except ImportError:
    try:
        from astrbot.api.event.filter import event_message
    except ImportError:
        def event_message(func): return func

logger = logging.getLogger("astrbot")

@register("astrbot_plugin_mention_reply", "qingcai", "群友专属回复助手", "1.4.8")
class MentionReplyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.db_path = os.path.join("data", "mention_reply_config.json")
        self.config = self._load_config()
        logger.info("===== [嘴替助手] 1.4.8 准备就绪 =====")

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

    # --- 核心功能：自动回复 ---
    @event_message
    async def handle_mentions(self, event: AstrMessageEvent):
        if not self.config.get("enabled", True): return
        if event.message_str.startswith("/"): return

        # 获取消息链
        chain = event.get_messages()
        for seg in chain:
            t_id = ""
            if hasattr(seg, 'type') and seg.type == "at":
                t_id = str(seg.data.get("qq") or seg.data.get("user_id", ""))
            elif hasattr(seg, 'qq') and seg.qq:
                t_id = str(seg.qq)
            
            if t_id and t_id in self.config.get("replies", {}):
                reply_text = self.config["replies"][t_id]
                logger.info(f"[嘴替匹配] 目标:{t_id}, 内容:{reply_text}")
                # 拦截并发送
                event.stop_event()
                await event.send_message([reply_text])
                return

    # --- 指令：帮助 ---
    @filter.command("嘴替帮助")
    async def help_cmd(self, event: AstrMessageEvent):
        yield event.plain_result(
            "🤖 **群友嘴替助手**\n"
            "1. `/setreply @某人 回复内容` (设置)\n"
            "2. `/delreply @某人` (删除)\n"
            "3. `/listreply` (列表)\n"
            "4. `/toggle` (总开关)"
        )

    # --- 指令：设置 (优化内容抓取) ---
    @filter.command("setreply")
    async def set_reply(self, event: AstrMessageEvent, *, content: str = ""):
        if str(event.get_sender_id()) not in self.config.get("admin_qq", []):
            yield event.plain_result("❌ 权限不足")
            return

        # 1. 找被 @ 的人
        target_id = ""
        at_text = "" # 用来从内容里扣除 @ 文本
        for seg in event.get_messages():
            if (hasattr(seg, 'type') and seg.type == "at") or (hasattr(seg, 'qq') and seg.qq):
                target_id = str(getattr(seg, 'qq', seg.data.get("qq") if hasattr(seg, 'data') else ""))
                # 获取 @ 的原始文本（如 @小青菜 ）
                at_text = str(seg) 
                break
        
        if not target_id:
            yield event.plain_result("⚠️ 请务必在指令中 @ 一个用户。")
            return

        # 2. 清理内容：去掉 @ 文本本身，剩下才是回复语
        # 比如输入: /setreply @张三 你好呀
        # content 可能是 "@张三 你好呀"
        final_reply = content.replace(at_text, "").strip()
        
        if not final_reply:
            yield event.plain_result("⚠️ 格式：/setreply @用户 回复内容")
            return

        self.config["replies"][target_id] = final_reply
        self._save_config()
        yield event.plain_result(f"✅ 设置成功！有人 @{target_id} 时，我会代答：\n{final_reply}")

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
            yield event.plain_result(f"✅ 已删除针对 {target_id} 的代答。")

    @filter.command("listreply")
    async def list_reply(self, event: AstrMessageEvent):
        if not self.config["replies"]:
            yield event.plain_result("📭 列表为空")
        else:
            res = "📋 列表:\n" + "\n".join([f"{k}: {v}" for k, v in self.config["replies"].items()])
            yield event.plain_result(res)

    @filter.command("toggle")
    async def toggle_cmd(self, event: AstrMessageEvent):
        if str(event.get_sender_id()) not in self.config.get("admin_qq", []): return
        self.config["enabled"] = not self.config.get("enabled", True)
        self._save_config()
        yield event.plain_result(f"✅ 嘴替助手已{'开启' if self.config['enabled'] else '关闭'}。")
