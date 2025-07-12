import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List

import aiosmtplib
from astrbot.api import logger, AstrBotConfig
from astrbot.api.event import AstrMessageEvent

from .templates import (
    generate_message_exception_email,
    generate_batch_message_exception_email,
)


class EmailService:
    """處理郵件發送服務"""

    def __init__(self, config: AstrBotConfig):
        # 如果 config 為 None，提供一個空的實例以安全地 .get()
        safe_config = config or AstrBotConfig({})
        smtp_settings = safe_config.get("smtp_settings", {})
        notification_filtering = safe_config.get("notification_filtering", {})

        self.smtp_server = smtp_settings.get("smtp_server", "").strip()
        self.smtp_port = smtp_settings.get("smtp_port", 587)
        self.smtp_username = smtp_settings.get("smtp_username", "")
        # 發件人地址，如果未配置，則回退使用登錄用戶名
        self.sender_address = smtp_settings.get("sender_address") or self.smtp_username
        self.smtp_settings = smtp_settings  # 保存設置以供後續使用
        self.recipient_emails = notification_filtering.get("recipient_emails", [])
        self.enable_ssl = smtp_settings.get("enable_ssl", True)

    async def send_email_async(self, subject: str, body: str):
        """異步發送郵件"""
        smtp_password = self.smtp_settings.get("smtp_password", "")
        if not all(
            [
                self.smtp_server,
                self.smtp_username,
                smtp_password,
                self.recipient_emails,
            ]
        ):
            logger.warning("郵件服務未配置，無法發送郵件。")
            return

        msg = MIMEMultipart()
        msg["From"] = self.sender_address
        msg["To"] = ", ".join(self.recipient_emails)
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html", "utf-8"))

        try:
            # Brevo 在 587 端口上使用 STARTTLS
            # 我們需要連接，然後手動升級到 TLS 並登錄
            smtp_client = aiosmtplib.SMTP(
                hostname=self.smtp_server, port=self.smtp_port
            )
            async with smtp_client:
                if self.enable_ssl:
                    try:
                        await smtp_client.starttls()
                    except aiosmtplib.SMTPException as e:
                        # 如果連線已自動升級到 TLS，aiosmtplib 會引發此異常。
                        # 我們可以安全地忽略它並繼續。
                        if "already using tls" not in str(e).lower():
                            raise  # 重新引發其他非預期的 SMTP 錯誤

                # 使用您的 Brevo 登錄名和 SMTP 密鑰進行驗證
                await smtp_client.login(self.smtp_username, smtp_password)

                # 發送郵件
                await smtp_client.send_message(msg)
            logger.info(f"成功發送異常郵件至: {', '.join(self.recipient_emails)}")
        except Exception as e:
            logger.error(
                f"發送郵件失敗，請檢查 SMTP 配置和網路通信。異常類型: {type(e).__name__}"
            )


class ExceptionProcessor:
    """處理和管理異常報告"""

    def __init__(
        self,
        config: AstrBotConfig,
        email_service: EmailService,
        star_instance,
        main_loop: asyncio.AbstractEventLoop,
        data_dir: "Path",
    ):
        self.star_instance = star_instance
        self.email_service = email_service
        self.main_loop = main_loop
        self.data_dir = data_dir
        safe_config = config or AstrBotConfig({})
        rate_limit_batching = safe_config.get("rate_limit_batching", {})

        self.max_emails_per_hour = rate_limit_batching.get("max_emails_per_hour", 10)
        self.enable_batching = rate_limit_batching.get("enable_batching", True)
        self.batch_window_seconds = rate_limit_batching.get("batch_window_seconds", 60)
        self.message_buffer: List[Dict[str, Any]] = []
        self.batch_send_task: asyncio.Task = None

        self.email_counter = {
            "count": 0,
            "reset_time": datetime.now() + timedelta(hours=1),
        }

        self.exception_cache: List[Dict[str, Any]] = []

    def _reset_email_counter_if_needed(self):
        """如果需要，重置郵件計數器"""
        if datetime.now() >= self.email_counter["reset_time"]:
            self.email_counter["count"] = 0
            self.email_counter["reset_time"] = datetime.now() + timedelta(hours=1)

    def _is_rate_limited(self) -> bool:
        """檢查是否達到每小時郵件發送上限"""
        self._reset_email_counter_if_needed()
        return self.email_counter["count"] >= self.max_emails_per_hour

    async def stop(self):
        """終止處理器，取消任何正在運行的批處理任務並處理剩餘的緩衝區。"""
        logger.info("正在停止 ExceptionProcessor...")
        # 如果存在正在運行的批處理任務，等待其完成，以避免競態條件
        if self.batch_send_task and not self.batch_send_task.done():
            logger.info("等待當前的批處理任務完成...")
            try:
                # 不直接取消，而是等待它自然結束
                await self.batch_send_task
            except asyncio.CancelledError:
                logger.warning("批處理任務在等待期間被取消。")
            except Exception as e:
                logger.error(f"[ErrorMonitor] 等待批處理任務完成時發生意外錯誤: {e}", exc_info=True)

        # 檢查緩衝區中是否在任務執行後仍有剩餘日誌（理論上不應該，但作為安全保障）
        if self.message_buffer:
            logger.info(f"插件終止前，處理剩餘的 {len(self.message_buffer)} 則異常。")
            messages_to_send = list(self.message_buffer)
            self.message_buffer.clear()

            if not self._is_rate_limited():
                self.email_counter["count"] += 1
                subject, body = generate_batch_message_exception_email(messages_to_send)
                await self.email_service.send_email_async(subject, body)
                logger.info("已成功發送剩餘的異常報告。")
            else:
                logger.warning("已達到郵件發送上限，剩餘的異常報告將被捨棄。")

    async def process_message_exception(self, event: AstrMessageEvent, keyword: str):
        """處理來自訊息的異常"""
        exception_info = {
            "type": "message",
            "platform": event.get_platform_name(),
            "sender": event.get_sender_name(),
            "sender_id": event.get_sender_id(),
            "group_id": event.get_group_id(),
            "message": event.get_message_str(),
            "keyword": keyword,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        if not self.enable_batching:
            await self._process_internal(exception_info)
            return

        # --- 批處理邏輯 ---
        self.message_buffer.append(exception_info)

        # 如果沒有正在運行的發送任務，則創建一個
        if self.batch_send_task is None or self.batch_send_task.done():
            logger.info(
                f"檢測到第一個訊息異常，已啟動 {self.batch_window_seconds} 秒的批處理窗口。"
            )
            self.batch_send_task = self.main_loop.create_task(
                self._send_batch_email_after_delay()
            )

    async def _send_batch_email_after_delay(self):
        """等待指定時間後，發送批次郵件"""
        try:
            await asyncio.sleep(self.batch_window_seconds)

            if not self.message_buffer:
                return

            # 複製緩存並立即清空，防止新日誌在處理期間進入
            messages_to_send = list(self.message_buffer)
            self.message_buffer.clear()

            if self._is_rate_limited():
                logger.warning(
                    f"已達到每小時郵件發送上限，本次批次的 {len(messages_to_send)} 則異常將被捨棄。"
                )
                return

            self.email_counter["count"] += 1
            logger.info(
                f"批處理窗口結束，準備發送 {len(messages_to_send)} 則異常的匯總郵件。"
            )
            subject, body = generate_batch_message_exception_email(messages_to_send)
            await self.email_service.send_email_async(subject, body)
        except Exception as e:
            logger.error(f"[ErrorMonitor] 批處理郵件發送任務失敗: {e}", exc_info=True)

    async def _process_internal(self, exception_info: Dict[str, Any]):
        """內部處理邏輯，判斷是否發送郵件"""
        self.exception_cache.append(exception_info)
        if len(self.exception_cache) > 100:  # 防止快取過大
            self.exception_cache.pop(0)

        logger.debug("[ErrorMonitor] 正在處理異常...")

        if self._is_rate_limited():
            logger.warning("已達到每小時郵件發送上限，暫不發送郵件。")
            return

        # 更新計數器
        self.email_counter["count"] += 1

        subject, body = generate_message_exception_email(
            exception_info, self.exception_cache
        )
        await self.email_service.send_email_async(subject, body)
