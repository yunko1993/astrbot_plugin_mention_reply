import json
import os
from astrbot.api.event import filter
from astrbot.api.star import Context, Star, register
from astrbot.core.platform import AstrMessageEvent # 这里的导入路径必须和你 DNF 插件一致
from astrbot.api.event.filter import event_message

@register("astrbot_plugin_mention_reply", "qingcai", "群友专属回复助手", "1.3.6")
class MentionReplyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 配置文件路径，确保在 data 目录下
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

    # --- 监听所有消息 ---
    @event_message
    async def handle_all_message(self, event: AstrMessageEvent):
        if not self.config.get("enabled", True): return
        
        # 如果是指令（以/开头），这个函数不处理，交给下面的 filter 处理
        msg_str = event.get_result().get_plain_text() if hasattr(event, 'get_result') else str(event.message_obj)
        if msg_str.startswith("/"): return

        # 获取消息链
        chain = event.get_messages()
        for seg in chain:
            # 这里的 seg.type == "at" 是 OneBot v11 的标准
            if hasattr(seg, 'type') and seg.type == "at":
                target_id = str(seg.data.get("qq") or seg.data.get("user_id", ""))
                
                # 如果这个 QQ 在名单里
                if target_id in self.config.get("replies", {}):
                    reply_text = self.config["replies"][target_id]
                    yield event.plain_result(reply_text)
                    # 这里的 yield 会自动发送并尝试停止后续逻辑

    # --- 指令：帮助菜单 ---
    @filter.command("嘴替帮助")
    async def help_cmd(self, event: AstrMessageEvent):
        # 如果这个 yield 能出来，说明插件加载成功了
        result = [
            "🤖 **嘴替助手控制台**",
            "--------------------------",
            "1. /setreply @用户 回复内容",
            "2. /delreply @用户 (删除设置)",
            "3. /listreply (查看当前列表)",
            "--------------------------"
        ]
        yield event.plain_result("\n".join(result))

    # --- 指令：设置回复 ---
    @filter.command("setreply")
    async def set_reply(self, event: AstrMessageEvent, *, content: str = ""):
        sender_id = str(event.get_sender_id())
        if sender_id not in self.config.get("admin_qq", []):
            yield event.plain_result("❌ 你没有管理权限。")
            return

        # 从消息里找被 @ 的人
        target_id = ""
        for seg in event.get_messages():
            if hasattr(seg, 'type') and seg.type == "at":
                target_id = str(seg.data.get("qq") or seg.data.get("user_id", ""))
                break
        
        if not target_id or not content:
            yield event.plain_result("⚠️ 格式：/setreply @用户 回复内容")
            return

        # 存入配置
        self.config["replies"][target_id] = content.strip()
        self._save_config()
        yield event.plain_result(f"✅ 已成功设置 QQ:{target_id} 的嘴替回复。")

    # --- 指令：查看列表 ---
    @filter.command("listreply")
    async def list_reply(self, event: AstrMessageEvent):
        replies = self.config.get("replies", {})
        if not replies:
            yield event.plain_result("📭 嘴替列表目前是空的。")
            return
        
        res = ["📋 当前嘴替列表:"]
        for q, t in replies.items():
            res.append(f"QQ:{q} -> {t}")
        yield event.plain_result("\n".join(res))
