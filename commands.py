import aiosmtplib
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent
from astrbot.core.message.message_event_result import MessageChain
from astrbot.core.message.components import Plain

from .services import EmailService, ExceptionProcessor
from .templates import generate_test_email


async def handle_exception_status(
    event: AstrMessageEvent, processor: ExceptionProcessor, email_service: EmailService
):
    """處理 'exception_status' 指令，顯示插件狀態"""
    status_info = {
        "郵件設定": "已設定" if email_service.sender_address else "未設定",
        "本週期已寄送郵件": f"{processor.email_counter['count']}/{processor.max_emails_per_hour}",
        "異常快取數量": len(processor.exception_cache),
    }

    status_text = "異常監控插件狀態：\n"
    for key, value in status_info.items():
        status_text += f"• {key}: {value}\n"

    await event.send(MessageChain([Plain(text=status_text)]))


async def handle_clear_cache(event: AstrMessageEvent, processor: ExceptionProcessor):
    """處理 'clear_exception_cache' 指令，清除異常快取"""
    cache_count = len(processor.exception_cache)
    processor.exception_cache.clear()
    await event.send(MessageChain([Plain(text=f"已清除 {cache_count} 筆異常快取記錄")]))


async def handle_test_email(event: AstrMessageEvent, email_service: EmailService):
    """處理 'test_exception_email' 指令，寄送測試郵件"""
    event_info = {
        "platform": event.get_platform_name(),
        "sender_name": event.get_sender_name(),
        "sender_id": event.get_sender_id(),
    }
    subject, body = generate_test_email(event_info)

    try:
        await email_service.send_email_async(subject, body)
        await event.send(MessageChain([Plain(text="測試郵件已寄出，請檢查收件匣。")]))
    except aiosmtplib.SMTPException as e:
        logger.error(f"[ErrorMonitor] 測試郵件 SMTP 錯誤: {e}", exc_info=True)
        await event.send(
            MessageChain(
                [Plain(text="測試郵件寄送失敗：SMTP 服務錯誤，請檢查後台日誌。")]
            )
        )
    except Exception as e:
        logger.error(f"[ErrorMonitor] 寄送測試郵件時發生未知錯誤: {e}", exc_info=True)
        await event.send(MessageChain([Plain(text="測試郵件寄送失敗：發生未知錯誤。")]))
