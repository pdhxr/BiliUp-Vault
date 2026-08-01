import threading
import webbrowser


def open_browser_after_start(url: str) -> None:
    timer = threading.Timer(0.8, webbrowser.open, args=(url,))
    timer.daemon = True
    timer.start()
