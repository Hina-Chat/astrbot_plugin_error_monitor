import html
from datetime import datetime
from typing import Dict, Any, List

HTML_EMAIL_STYLE = """\
<style>
    body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji";
        margin: 0;
        padding: 0;
        background-color: #f6f8fa;
        color: #24292e;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }
    .email-wrapper {
        padding: 32px;
    }
    .container {
        max-width: 700px;
        margin: 0 auto;
        background-color: #ffffff;
        border: 1px solid #d0d7de;
        border-radius: 6px;
    }
    .header {
        padding: 24px;
        border-bottom: 1px solid #d0d7de;
    }
    .content {
        padding: 24px;
    }
    h2 {
        font-size: 22px;
        font-weight: 600;
        margin: 0 0 16px 0;
        padding: 0;
    }
    h3 {
        font-size: 16px;
        font-weight: 600;
        margin-top: 24px;
        margin-bottom: 8px;
        border-bottom: 1px solid #d0d7de;
        padding-bottom: 8px;
    }
    .msg-h2 { color: #9a6700; }
    .batch-h2 { color: #0969da; }
    .test-h2 { color: #1a7f37; }
    p {
        margin-top: 0;
        margin-bottom: 16px;
        line-height: 1.5;
    }
    table {
        border-collapse: collapse;
        width: 100%;
        margin-top: 8px;
        margin-bottom: 16px;
        border: 1px solid #d0d7de;
        border-radius: 6px;
        overflow: hidden;
    }
    th, td {
        padding: 12px 16px;
        text-align: left;
        border-bottom: 1px solid #d0d7de;
    }
    th {
        background-color: #f6f8fa;
        font-weight: 600;
    }
    tr:last-child th,
    tr:last-child td {
        border-bottom: none;
    }
    pre {
        background-color: #161b22;
        color: #c9d1d9;
        padding: 16px;
        border-radius: 6px;
        white-space: pre-wrap;
        word-wrap: break-word;
        font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, Courier, monospace;
        font-size: 13px;
        line-height: 1.6;
    }
    hr {
        border: none;
        border-top: 1px solid #d0d7de;
        margin: 24px 0;
    }
    .footer {
        padding: 16px 24px;
        font-size: 12px;
        color: #57606a;
        text-align: center;
        border-top: 1px solid #d0d7de;
        background-color: #f6f8fa;
    }
</style>
"""


def generate_message_exception_email(
    exception_info: Dict[str, Any], recent_logs: List[Dict[str, Any]]
) -> (str, str):
    """產生訊息異常的郵件主旨和內容 (HTML)"""
    subject = "【AstrBot 訊息異常回報】"

    recent_logs_html = "".join(
        f"<tr><td>{html.escape(str(log.get('timestamp')))}</td><td>{html.escape(str(log.get('message', ''))[:100])}...</td></tr>"
        for log in reversed(recent_logs[-5:])
    )

    body = f"""\
    <html>
        <head>{HTML_EMAIL_STYLE}</head>
        <body>
            <div class="email-wrapper">
                <div class="container">
                    <div class="header">
                        <h2 class="msg-h2">AstrBot 訊息異常回報</h2>
                    </div>
                    <div class="content">
                        <p>收到一則可能包含異常資訊的回報，詳細資訊如下：</p>
                        <table>
                            <tr><th>時間</th><td>{html.escape(str(exception_info.get("timestamp")))}</td></tr>
                            <tr><th>平台</th><td>{html.escape(str(exception_info.get("platform")))}</td></tr>
                            <tr><th>使用者</th><td>{html.escape(str(exception_info.get("sender")))} (ID: {html.escape(str(exception_info.get("sender_id")))})</td></tr>
                            <tr><th>群組</th><td>{html.escape(str(exception_info.get("group_id", "N/A")))}</td></tr>
                            <tr><th>關鍵字</th><td>{html.escape(str(exception_info.get("keyword")))}</td></tr>
                        </table>
                        <h3>原始訊息</h3>
                        <pre>{html.escape(str(exception_info.get("message")))}</pre>
                        <h3>最近 5 筆日誌快取</h3>
                        <table>
                            <tr><th>時間</th><th>資訊</th></tr>
                            {recent_logs_html}
                        </table>
                    </div>
                    <div class="footer">Generated by AstrBot Error Monitor Plugin</div>
                </div>
            </div>
        </body>
    </html>
    """
    return subject, body


def generate_batch_message_exception_email(
    exceptions: List[Dict[str, Any]],
) -> (str, str):
    """產生批次訊息異常的郵件主旨和內容 (HTML)"""
    subject = "【AstrBot 批次異常回報】"

    exceptions_html = ""
    for i, exc_info in enumerate(exceptions):
        message_context = (
            "GP"
            if exc_info.get("group_id") and exc_info.get("group_id") != "N/A"
            else "DM"
        )
        exceptions_html += f"""\
            <h3>異常 #{i + 1}</h3>
            <table>
                <tr><th>時間</th><td>{html.escape(str(exc_info.get("timestamp")))}</td></tr>
                <tr><th>平台</th><td>{html.escape(str(exc_info.get("platform")))}</td></tr>
                <tr><th>來源</th><td>{html.escape(message_context)}</td></tr>
                <tr><th>使用者</th><td>{html.escape(str(exc_info.get("sender")))} (ID: {html.escape(str(exc_info.get("sender_id")))})</td></tr>
                <tr><th>群組</th><td>{html.escape(str(exc_info.get("group_id", "N/A")))}</td></tr>
                <tr><th>關鍵字</th><td>{html.escape(str(exc_info.get("keyword")))}</td></tr>
            </table>
            <pre>{html.escape(str(exc_info.get("message")))}</pre>
            {"<hr>" if i < len(exceptions) - 1 else ""}
        """

    body = f"""\
    <html>
        <head>{HTML_EMAIL_STYLE}</head>
        <body>
            <div class="email-wrapper">
                <div class="container">
                    <div class="header">
                        <h2 class="batch-h2">AstrBot 批次異常回報</h2>
                    </div>
                    <div class="content">
                        <p>在最近的批處理窗口內，共收集到 <strong>{len(exceptions)}</strong> 則異常。詳細資訊如下：</p>
                        {exceptions_html}
                    </div>
                    <div class="footer">Generated by AstrBot Error Monitor Plugin</div>
                </div>
            </div>
        </body>
    </html>
    """

    return subject, body


def generate_test_email(event_info: Dict[str, Any]) -> (str, str):
    """產生測試郵件的主旨和內容 (HTML)"""
    subject = "【AstrBot 異常監控】測試郵件"

    body = f"""\
    <html>
        <head>{HTML_EMAIL_STYLE}</head>
        <body>
            <div class="email-wrapper">
                <div class="container">
                    <div class="header">
                        <h2 class="test-h2">AstrBot 異常監控測試郵件</h2>
                    </div>
                    <div class="content">
                        <p>如果您收到此郵件，表示您的郵件設定正確無誤。</p>
                        <hr>
                        <table>
                            <tr><th>測試時間</th><td>{html.escape(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))}</td></tr>
                            <tr><th>測試平台</th><td>{html.escape(str(event_info.get("platform")))}</td></tr>
                            <tr><th>測試使用者</th><td>{html.escape(str(event_info.get("sender_name")))} (ID: {html.escape(str(event_info.get("sender_id")))})</td></tr>
                        </table>
                    </div>
                    <div class="footer">Generated by AstrBot Error Monitor Plugin</div>
                </div>
            </div>
        </body>
    </html>
    """
    return subject, body
