#!/usr/bin/env python3
"""Windows桌面通知：网站已更新"""
import subprocess, sys

title = sys.argv[1] if len(sys.argv) > 1 else "行业雷达"
body = sys.argv[2] if len(sys.argv) > 2 else "网站已更新，Ctrl+Shift+R 刷新查看"

ps = f'''
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
$t = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$t.GetElementsByTagName("text")[0].AppendChild($t.CreateTextNode("{title}")) | Out-Null
$t.GetElementsByTagName("text")[1].AppendChild($t.CreateTextNode("{body}")) | Out-Null
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("行业雷达").Show($t)
'''
subprocess.run(['powershell', '-Command', ps], capture_output=True, timeout=5)
