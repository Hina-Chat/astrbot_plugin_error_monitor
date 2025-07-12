# Error Monitor

為 AstrBot 設計的錯誤報告插件。它能捕獲由 [Immersive Error](https://github.com/Hina-Chat/astrbot_plugin_immersive_error) 產生的異常，並提供成熟的通知策略，包括郵件通知、速率限制與批次處理，旨在幫助管理員及時發現問題，同時避免資訊轟炸。

## 核心功能

- **雙模式錯誤捕獲**：
  - **被動監聽**：自動監聽並處理由其他插件附加到事件物件上的 `reported_error` 屬性，實現非侵入式監控。
  - **主動 API**：提供 `report_error` 函式，讓插件開發者可以主動、精確地報告特定錯誤。
- **智慧型通知策略**：
  - **速率限制**：設定每小時最大郵件發送數量，防止在系統性故障時收到大量重複郵件。
  - **批次處理**：可將短時間內（例如 60 秒）發生的所有異常合併成一封匯總郵件，在高併發錯誤場景下極為有效。
- **詳細郵件報告**：
  - 發送格式精美的 HTML 郵件，內容包含詳細的錯誤上下文（觸發平台、使用者、原始訊息等）。
  - 單一錯誤報告會附上最近的錯誤歷史，方便追蹤問題演變。
- **靈活的配置**：從總開關到 SMTP 伺服器，再到通知策略的每個細節，所有功能皆可客製化。
- **管理員指令**：提供指令方便查詢插件狀態、清除快取和測試郵件設定。

## 技術架構

插件的核心由 `ExceptionMonitorPlugin`, `EmailService`, 和 `ExceptionProcessor` 三個服務構成，工作流程如下：

1.  **錯誤入口 (`ExceptionMonitorPlugin`)**：作為插件總入口，透過被動 (`consume_reported_error`) 和主動 (`report_error`) 兩種方式接收錯誤。
2.  **處理核心 (`ExceptionProcessor`)**：對收到的錯誤進行批次處理、速率限制和冷卻檢查，決定是否觸發通知。
3.  **郵件服務 (`EmailService`)**：根據設定建立安全的 SMTP 連線，並異步發送由 `templates.py` 產生的 HTML 郵件。

## 安裝與設定

所有配置選項皆定義於 `_conf_schema.json` 中，可透過 AstrBot 的設定介面進行修改。

| 分類 | 設定項 | 類型 | 預設值 | 說明 |
| :--- | :--- | :--- | :--- | :--- |
| **通用** | `enable_monitoring` | bool | `true` | 插件的總開關。關閉後將停止所有監控和報告功能。 |
| **SMTP 伺服器** | `smtp_server` | string | | SMTP 伺服器位址 (例如: `smtp.gmail.com`)。 |
| | `smtp_port` | int | `587` | SMTP 通訊埠，`587` (TLS) 是最常見的選擇。 |
| | `smtp_username` | string | | SMTP 登入帳戶。 |
| | `smtp_password` | string | | 對應的密碼或應用程式專用金鑰。 |
| | `sender_address` | string | | 發件人郵箱地址。如果留空，將使用 `smtp_username`。 |
| | `enable_ssl` | bool | `true` | 是否啟用 ` SSL/TLS ` 加密。 |
| **通知與過濾** | `recipient_emails` | list | `[]` | 接收錯誤通知的郵件地址清單。 |
| **頻率與批次** | `max_emails_per_hour` | int | `10` | 每小時最多發送的郵件數量。 |
| | `enable_batching` | bool | `true` | 是否啟用批次處理模式。 |
| | `batch_window_seconds`| int | `60` | 批次處理的時間窗口（秒）。 |

## 使用指南

### 管理員指令

| 指令 | 權限等級 | 功能 |
| :--- | :--- | :--- |
| `test_error_email` | Admin | 發送一封測試郵件，用於驗證 SMTP 設定是否正確。 |
| `exception_status` | Admin | 顯示插件當前的運行狀態，包括郵件設定、已發送計數和快取數量。 |
| `clear_exception_cache` | Admin | 手動清除插件內部記錄的所有異常快取。 |

### 開發者整合

您可以透過以下兩種方式將您的插件與 `error-monitor` 整合：

#### 方式一：被動報告 (建議)

這是最簡單且非侵入式的整合方式。在您的事件處理函式中，只需將一個代表錯誤類型的string關鍵字賦值給 `event.reported_error` 即可。

```python
from astrbot.api.event import AstrMessageEvent

async def my_command_handler(event: AstrMessageEvent):
    try:
        # ... 您的程式碼 ...
        result = risky_operation()
        if not result:
            # 將錯誤關鍵字附加到事件上
            event.reported_error = "MyPluginDataFetchFailed"
            await event.reply("資料獲取失敗，請稍後再試。")
            return
    except Exception:
        # 對於真正的 Python 異常，也可以報告
        event.reported_error = "MyPluginCriticalError"
        await event.reply("插件發生內部錯誤，已記錄。")
```

#### 方式二：主動呼叫 API

若需更精確的控制，可直接獲取 `error-monitor` 插件實例並呼叫其 `report_error` API。

```python
from astrbot.api import get_star
from astrbot.api.event import AstrMessageEvent

async def my_command_handler(event: AstrMessageEvent):
    try:
        # ... 您的程式碼 ...
        risky_operation()
    except Exception:
        # 獲取插件實例
        if error_monitor := get_star("error-monitor"):
            # 主動呼叫 API
            await error_monitor.report_error(event, keyword="MyPluginAPICallFailure")
```
