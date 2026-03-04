import json
import os
import logging
import re
from astrbot.api.event import filter
from astrbot.api.star import Context, Star, register
from astrbot.core.platform import AstrMessageEvent

logger = logging.getLogger("astrbot")

@register("astrbot_plugin_mention_reply", "qingcai", "群友专属回复助手", "1.8.0")
class MentionReplyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 配置文件存放在插件自身目录下
        self.db_path = os.path.join(os.path.dirname(__file__), "mention_reply_config.json")
        self.config = self._load_config()
        logger.info(f"===== [群友嘴替助手] 已加载，数据路径: {self.db_path} =====")

    def _load_config(self):
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except: pass
        # 默认填入你的 QQ 作为初始管理员
        return {"enabled": True, "admin_qq":["1023902556"], "replies": {}}

    def _save_config(self):
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=4)

    # --- 核心监听：拦截被 @ 的消息 ---
    @filter.event_message_type(filter.EventMessageType.ALL)
    async def handle_mentions(self, event: AstrMessageEvent):
        if not self.config.get("enabled", True): return
        
        msg_str = getattr(event, 'message_str', '')
        # 忽略指令类消息，避免冲突
        if msg_str.startswith("/") or "setreply" in msg_str or "delreply" in msg_str: 
            return

        for seg in event.get_messages():
            t_id = ""
            if hasattr(seg, 'type') and seg.type == "at":
                t_id = str(seg.data.get("qq") or seg.data.get("user_id", ""))
            elif hasattr(seg, 'qq') and seg.qq:
                t_id = str(seg.qq)
            
            if t_id and t_id in self.config.get("replies", {}):
                reply_text = self.config["replies"][t_id]
                logger.info(f"===== [嘴替助手] 拦截到 @{t_id}，触发代答: {reply_text} =====")
                
                # 发送回复
                yield event.plain_result(reply_text)
                # 截断事件，阻止大模型回复
                event.stop_event()
                return

    # --- 指令：帮助菜单 ---
    @filter.command("嘴替帮助")
    async def help_cmd(self, event: AstrMessageEvent):
        yield event.plain_result(
            "🤖 **嘴替助手控制台**\n"
            "1. `/setreply @某人 内容` (设置)\n"
            "2. `/delreply @某人` (删除)\n"
            "3. `/listreply` (列表)\n"
            "4. `/toggle` (总开关)"
        )

    # --- 指令：设置代答 ---
    @filter.command("setreply")
    async def set_reply(self, event: AstrMessageEvent):
        if str(event.get_sender_id()) not in self.config.get("admin_qq",[]): return

        target_id = ""
        for seg in event.get_messages():
            if (hasattr(seg, 'type') and seg.type == "at") or (hasattr(seg, 'qq') and seg.qq):
                target_id = str(getattr(seg, 'qq', seg.data.get("qq") if hasattr(seg, 'data') else ""))
                if target_id: break
        
        if not target_id:
            yield event.plain_result("⚠️ 识别失败！请务必在指令中 @ 一个用户。")
            return

        # 提取原始消息字符串
        msg = getattr(event, 'message_str', '')
        
        # 暴力洗牌：清洗所有可能的指令前缀和 At 标记
        msg = re.sub(r'^/?setreply\s*', '', msg, flags=re.IGNORECASE)
        msg = re.sub(r'\[At:\d+\]', '', msg)
        msg = re.sub(r'<at qq="\d+"/>', '', msg)
        msg = re.sub(r'\[CQ:at,qq=\d+\]', '', msg)
        msg = re.sub(r'@\S+\(\d+\)', '', msg)
        msg = re.sub(r'@\S+', '', msg)
        
        reply = msg.strip()
        
        if not reply:
            yield event.plain_result(f"⚠️ 识别到用户 {target_id}，但提取台词为空。")
            return

        self.config["replies"][target_id] = reply
        self._save_config()
        yield event.plain_result(f"✅ 设置成功！有人 @{target_id} 时，我会代答：\n{reply}")

    # --- 指令：删除代答 ---
    @filter.command("delreply")
    async def del_reply(self, event: AstrMessageEvent):
        if str(event.get_sender_id()) not in self.config.get("admin_qq",[]): return
        target_id = ""
        for seg in event.get_messages():
            if (hasattr(seg, 'type') and seg.type == "at") or (hasattr(seg, 'qq') and seg.qq):
                target_id = str(getattr(seg, 'qq', seg.data.get("qq") if hasattr(seg, 'data') else ""))
                break
        if target_id in self.config["replies"]:
            del self.config["replies"][target_id]
            self._save_config()
            yield event.plain_result(f"✅ 已删除针对 {target_id} 的代答。")
        else:
            yield event.plain_result("❌ 该用户目前没有设置代答。")

    # --- 指令：查看列表 ---
    @filter.command("listreply")
    async def list_reply(self, event: AstrMessageEvent):
        if not self.config["replies"]:
            yield event.plain_result("📭 当前嘴替列表为空")
        else:
            res = "📋 当前嘴替列表:\n" + "\n".join([f"• {k}: {v}" for k, v in self.config["replies"].items()])
            yield event.plain_result(res)

    # --- 指令：全局开关 ---
    @filter.command("toggle")
    async def toggle_cmd(self, event: AstrMessageEvent):
        if str(event.get_sender_id()) not in self.config.get("admin_qq", []): return
        self.config["enabled"] = not self.config.get("enabled", True)
        self._save_config()
        status = '🟢 已开启' if self.config['enabled'] else '🔴 已关闭'
        yield event.plain_result(f"✅ 嘴替功能 {status}。")
