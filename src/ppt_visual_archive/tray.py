"""Windows notification-area controls for the per-user archive agent.

Windows-only imports are intentionally kept inside ``run_tray`` so PDF-only
non-Windows installs can import the package without pywin32.
"""

from __future__ import annotations

import os


def run_tray(runtime) -> None:
    """Run the Windows notification-area icon until Exit/Restart/process end."""
    if os.name != "nt":
        return

    import win32api
    import win32con
    import win32gui

    wm_tray = win32con.WM_USER + 20
    command_open = 1001
    command_scan = 1002
    command_settings = 1003
    command_logs = 1004
    command_restart = 1005
    command_exit = 1006

    def wnd_proc(hwnd, msg, wparam, lparam):
        if msg == wm_tray:
            if lparam == win32con.WM_LBUTTONDBLCLK:
                runtime.open_archive()
                return 0
            if lparam == win32con.WM_RBUTTONUP:
                menu = win32gui.CreatePopupMenu()
                status = runtime.status_snapshot().get("status", "unknown")
                win32gui.AppendMenu(menu, win32con.MF_STRING | win32con.MF_GRAYED, 0, f"Status: {status}")
                win32gui.AppendMenu(menu, win32con.MF_SEPARATOR, 0, "")
                win32gui.AppendMenu(menu, win32con.MF_STRING, command_open, "Open Archive")
                win32gui.AppendMenu(menu, win32con.MF_STRING, command_scan, "Scan Now")
                win32gui.AppendMenu(menu, win32con.MF_STRING, command_settings, "Settings")
                win32gui.AppendMenu(menu, win32con.MF_STRING, command_logs, "View Logs")
                win32gui.AppendMenu(menu, win32con.MF_SEPARATOR, 0, "")
                win32gui.AppendMenu(menu, win32con.MF_STRING, command_restart, "Restart")
                win32gui.AppendMenu(menu, win32con.MF_STRING, command_exit, "Exit")
                x, y = win32gui.GetCursorPos()
                win32gui.SetForegroundWindow(hwnd)
                win32gui.TrackPopupMenu(
                    menu,
                    win32con.TPM_LEFTALIGN | win32con.TPM_BOTTOMALIGN,
                    x,
                    y,
                    0,
                    hwnd,
                    None,
                )
                win32gui.PostMessage(hwnd, win32con.WM_NULL, 0, 0)
                return 0

        if msg == win32con.WM_COMMAND:
            command = win32api.LOWORD(wparam)
            if command == command_open:
                runtime.open_archive()
            elif command == command_scan:
                runtime.request_refresh()
            elif command == command_settings:
                runtime.open_settings()
            elif command == command_logs:
                try:
                    runtime.open_logs()
                except OSError:
                    pass
            elif command == command_restart:
                runtime.request_shutdown(restart=True)
                win32gui.DestroyWindow(hwnd)
            elif command == command_exit:
                runtime.request_shutdown(restart=False)
                win32gui.DestroyWindow(hwnd)
            return 0

        if msg == win32con.WM_DESTROY:
            try:
                win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, (hwnd, 0))
            finally:
                win32gui.PostQuitMessage(0)
            return 0

        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    instance = win32api.GetModuleHandle(None)
    class_name = "PowerPointVisualArchiveTray"
    wc = win32gui.WNDCLASS()
    wc.hInstance = instance
    wc.lpszClassName = class_name
    wc.lpfnWndProc = wnd_proc
    try:
        win32gui.RegisterClass(wc)
    except win32gui.error:
        pass

    hwnd = win32gui.CreateWindow(
        class_name,
        "PowerPoint Visual Archive",
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        instance,
        None,
    )
    icon = win32gui.LoadIcon(0, win32con.IDI_APPLICATION)
    notify = (
        hwnd,
        0,
        win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP,
        wm_tray,
        icon,
        "PowerPoint Visual Archive",
    )
    win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, notify)
    win32gui.PumpMessages()
