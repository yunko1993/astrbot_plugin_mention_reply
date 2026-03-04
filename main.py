import json
import os
import logging
from astrbot.api.event import filter
from astrbot.api.star import Context, Star, register
from astrbot.core.platform import AstrMessageEvent
from astrbot.api.event.filter import event_message

logger = logging.getLogger("astrbot")

@register("astrbot_plugin_mention_reply", "qingcai", "群友专属回复助手", "1.4.5")
class MentionReplyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.db_path = os.path.join("data", "mention_reply_config.json")
        self.config = self._load_config()
        logger.info("===== [嘴替助手] 完整版已加载 =====")

    def _load_config(self):
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return {"enabled": True, "admin_qq": ["1023902556"], "replies": {}}

    def _save_config(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=4)

    # --- 核心功能：监听所有消息 ---
    @event_message
    async def handle_replies(self, event: AstrMessageEvent):
        # 1. 检查全局开关
        if not self.config.get("enabled", True):
            return
        
        # 2. 如果是指令，交给 filter 处理，这里跳过
        if event.message_str.startswith("/"):
            return

        # 3. 遍历消息段寻找 At
        for seg in event.get_messages():
            # 兼容性判断：只要包含 qq 字段或是 at 类型
            t_id = ""
            if hasattr(seg, 'type') and seg.type == "at":
                t_id = str(seg.data.get("qq") or seg.data.get("user_id", ""))
            elif hasattr(seg, 'qq') and seg.qq: # 某些版本直接是 seg.qq
                t_id = str(seg.qq)
            
            if t_id and t_id in self.config.get("replies", {}):
                reply_text = self.config["replies"][t_id]
                event.stop_event() # 拦截，不让 AI 说话
                yield event.plain_result(reply_text)
                return

    # --- 指令：帮助菜单 ---
    @filter.command("嘴替帮助")
    async def help_cmd(self, event: AstrMessageEvent):
        status = "🟢 已开启" if self.config.get("enabled", True) else "🔴 已关闭"
        result = [
            f"🤖 **嘴替助手控制台** (当前:{status})",
            "--------------------------",
            "1. `/setreply @用户 内容` - 设置代答",
            "2. `/delreply @用户` - 删除代答",
            "3. `/listreply` - 查看列表",
            "4. `/toggle` - 开启/关闭插件",
            "--------------------------"
        ]
        yield event.plain_result("\n".join(result))

    # --- 指令：设置回复 ---
    @filter.command("setreply")
    async def set_reply(self, event: AstrMessageEvent, *, content: str = ""):
        if str(event.get_sender_id()) not in self.config.get("admin_qq", []):
            yield event.plain_result("❌ 权限不足")
            return

        target_id = ""
        # 改进的 At 解析逻辑
        for seg in event.get_messages():
            if (hasattr(seg, 'type') and seg.type == "at"):
                target_id = str(seg.data.get("qq") or seg.data.get("user_id", ""))
            elif hasattr(seg, 'qq') and seg.qq:
                target_id = str(seg.qq)
            
            if target_id: break
        
        if not target_id:
            yield event.plain_result("⚠️ 格式错误：请务必 @ 那个用户。")
            return

        # 从内容中剔除掉 @ 相关的文本，只保留回复语
        # content 已经是去掉指令后的部分了
        self.config["replies"][target_id] = content.strip()
        self._save_config()
        yield event.plain_result(f"✅ 已设置成功！\n当有人 @{target_id} 时，我会代答：\n{content.strip()}")

    # --- 指令：删除回复 ---
    @filter.command("delreply")
    async def del_reply(self, event: AstrMessageEvent):
        if str(event.get_sender_id()) not in self.config.get("admin_qq", []):
            return

        target_id = ""
        for seg in event.get_messages():
            if (hasattr(seg, 'type') and seg.type == "at") or (hasattr(seg, 'qq') and seg.qq):
                target_id = str(getattr(seg, 'qq', seg.data.get("qq") if hasattr(seg, 'data') else ""))
                break
        
        if target_id in self.config.get("replies", {}):
            del self.config["replies"][target_id]
            self._save_config()
            yield event.plain_result(f"✅ 已删除针对 QQ:{target_id} 的设置。")
        else:
            yield event.plain_result("❌ 该用户没有设置过嘴替。")

    # --- 指令：列表 ---
    @filter.command("listreply")
    async def list_reply(self, event: AstrMessageEvent):
        replies = self.config.get("replies", {})
        if not replies:
            yield event.plain_result("📭 列表为空。")
            return
        res = ["📋 嘴替列表:"]
        for q, t in replies.items():
            res.append(f"• {q} -> {t}")
        yield event.plain_result("\n".join(res))

    # --- 指令：开关 ---
    @filter.command("toggle")
    async def toggle_plugin(self, event: AstrMessageEvent):
        if str(event.get_sender_id()) not in self.config.get("admin_qq", []):
            return
        
        self.config["enabled"] = not self.config.get("enabled", True)
        self._save_config()
        status = "开启" if self.config["enabled"] else "关闭"
        yield event.plain_result(f"✅ 嘴替助手已{status}。")
