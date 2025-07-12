import asyncio
import re
from typing import Optional

from astrbot.api import logger, AstrBotConfig
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, StarTools
from astrbot.core.message.components import Plain
from astrbot.core.message.message_event_result import MessageChain

from .commands import (
    handle_clear_cache,
    handle_exception_status,
    handle_test_email,
)
from .services import EmailService, ExceptionProcessor


class ExceptionMonitorPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config or AstrBotConfig({})
        self.general_config = self.config.get("general", {})
        self.enable_monitoring = self.general_config.get("enable_monitoring", True)

        # 將服務初始化延遲到 initialize，因為 __init__ 是同步的
        self.email_service: Optional[EmailService] = None
        self.exception_processor: Optional[ExceptionProcessor] = None
        self.data_dir = None  # 在 initialize 中进行异步初始化

    async def initialize(self):
        """在插件啟用時初始化所有服務"""
        try:
            logger.info("正在初始化 Error Monitor 插件...")
            if not self.enable_monitoring:
                logger.info("Error Monitor 插件的監控功能已禁用。")
                return

            main_loop = asyncio.get_running_loop()
            self.data_dir = StarTools.get_data_dir()
            self.email_service = EmailService(self.config)
            self.exception_processor = ExceptionProcessor(
                self.config, self.email_service, self, main_loop, self.data_dir
            )

            logger.info("Error Monitor 插件已成功初始化。")
        except Exception as e:
            logger.error(f"[ErrorMonitor] CRITICAL: 插件初始化失敗: {e}", exc_info=True)
            self.exception_processor = None

    async def terminate(self):
        """插件終止時的操作"""
        if self.exception_processor:
            await self.exception_processor.stop()
        logger.info("Error Monitor 插件已卸載。")

    @filter.on_decorating_result(priority=1)  # 使用較低的優先級，確保在生產者之後執行
    async def consume_reported_error(self, event: AstrMessageEvent, *args, **kwargs):
        """監聽事件，消費由其他插件附加的錯誤報告。"""

        # 檢查事件對象上是否存在 'reported_error' 屬性
        reported_error = getattr(event, "reported_error", None)
        if reported_error:
            logger.debug("[ErrorMonitor] 檢測到事件上附加的錯誤報告，準備處理...")
            try:
                # 調用現有的核心處理方法
                if self.exception_processor:
                    logger.debug(
                        "[ErrorMonitor] ExceptionProcessor 實例存在，準備調用 process_message_exception..."
                    )
                    await self.exception_processor.process_message_exception(
                        event, reported_error
                    )
                    logger.info("[ErrorMonitor] 已成功處理來自事件的附加錯誤報告。")
                else:
                    logger.error(
                        "[ErrorMonitor] CRITICAL: ExceptionProcessor 實例為 None！插件初始化可能失敗。"
                    )
            except Exception as e:
                logger.error(f"[ErrorMonitor] 處理事件附加的錯誤報告時發生異常: {e}")

    async def report_error(self, event: AstrMessageEvent, keyword: str):
        """
        公開的 API，供其他插件呼叫以報告錯誤。
        """
        if not self.enable_monitoring or not self.exception_processor:
            return

        if keyword:
            logger.info(
                f"接收到來自 '{event.get_platform_name()}' 的錯誤報告，關鍵字: {keyword}"
            )
            await self.exception_processor.process_message_exception(event, keyword)

    # --- 指令處理器 ---
    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("test_error_email", re_flags=re.IGNORECASE)
    async def _test_error_email_command(self, event: AstrMessageEvent):
        """測試郵件發送功能"""
        if not self.enable_monitoring or not self.email_service:
            await event.send(
                MessageChain([Plain(text="監控功能未啟用或郵件服務未初始化。")])
            )
            return
        await handle_test_email(event, self.email_service)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("exception_status", re_flags=re.IGNORECASE)
    async def _exception_status_command(self, event: AstrMessageEvent):
        if not self.exception_processor or not self.email_service:
            await event.send(MessageChain([Plain(text="監控服務未初始化。")]))
            return
        await handle_exception_status(
            event, self.exception_processor, self.email_service
        )

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("clear_exception_cache", re_flags=re.IGNORECASE)
    async def _clear_cache_command(self, event: AstrMessageEvent):
        if not self.exception_processor:
            await event.send(MessageChain([Plain(text="監控服務未初始化。")]))
            return
        await handle_clear_cache(event, self.exception_processor)
