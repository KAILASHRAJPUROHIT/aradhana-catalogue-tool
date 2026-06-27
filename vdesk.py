"""
Virtual Desktop helper — moves Chrome windows to a dedicated desktop
so the user's main desktop stays completely clean.

Uses VirtualDesktopAccessor.dll (MIT licence, ~350KB).
"""
import ctypes, ctypes.wintypes, os, time

_DLL_PATH = os.path.join(os.path.dirname(__file__), "VirtualDesktopAccessor.dll")
_vda = None

def _load():
    global _vda
    if _vda is None and os.path.exists(_DLL_PATH):
        try:
            _vda = ctypes.CDLL(_DLL_PATH)
        except Exception:
            _vda = None
    return _vda


def get_desktop_count() -> int:
    d = _load()
    if not d: return 1
    try: return d.GetDesktopCount()
    except: return 1


def create_desktop() -> int:
    """Create a new virtual desktop and return its index."""
    d = _load()
    if not d: return 0
    try:
        before = d.GetDesktopCount()
        d.CreateDesktop()
        time.sleep(0.3)
        after = d.GetDesktopCount()
        return after - 1 if after > before else before - 1
    except:
        return 0


def get_current_desktop() -> int:
    d = _load()
    if not d: return 0
    try: return d.GetCurrentDesktopNumber()
    except: return 0


def go_to_desktop(idx: int):
    d = _load()
    if not d: return
    try: d.GoToDesktopNumber(idx)
    except: pass


def move_window_to_desktop(hwnd: int, idx: int) -> bool:
    d = _load()
    if not d: return False
    try:
        d.MoveWindowToDesktopNumber.restype  = ctypes.c_int
        d.MoveWindowToDesktopNumber.argtypes = [ctypes.wintypes.HWND, ctypes.c_int]
        r = d.MoveWindowToDesktopNumber(hwnd, idx)
        return r == 0
    except:
        return False


def get_window_desktop(hwnd: int) -> int:
    d = _load()
    if not d: return 0
    try:
        d.GetWindowDesktopNumber.restype  = ctypes.c_int
        d.GetWindowDesktopNumber.argtypes = [ctypes.wintypes.HWND]
        return d.GetWindowDesktopNumber(hwnd)
    except:
        return 0


def _find_chrome_hwnds(port_suffix: str) -> list:
    """Find all Chrome window handles — title or class matching."""
    import ctypes.wintypes as wt
    found = []
    def _cb(hwnd, _):
        buf = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, 256)
        t = buf.value.lower()
        if ("chrome" in t or "chatgpt" in t or "gemini" in t) and \
                ctypes.windll.user32.IsWindowVisible(hwnd):
            found.append(hwnd)
        return True
    CB = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    ctypes.windll.user32.EnumWindows(CB(_cb), 0)
    return found


# ── Public entry point ────────────────────────────────────────────────────────

_CATALOGUE_DESKTOP = None   # index of the dedicated desktop, once created

def setup_catalogue_desktop() -> int:
    """
    Create (or reuse) a dedicated virtual desktop for the catalogue Chromes.
    Returns the desktop index. Saves it globally so subsequent calls reuse it.
    """
    global _CATALOGUE_DESKTOP
    if _CATALOGUE_DESKTOP is not None:
        return _CATALOGUE_DESKTOP

    if not _load():
        print("VirtualDesktopAccessor.dll not available — skipping virtual desktop")
        _CATALOGUE_DESKTOP = 0
        return 0

    # Always create a fresh desktop at the end of the list
    idx = create_desktop()
    _CATALOGUE_DESKTOP = idx
    print(f"[vdesk] Catalogue desktop: {idx} (of {get_desktop_count()} total)")
    return idx


def push_chrome_to_catalogue_desktop():
    """
    Move all visible Chrome windows to the catalogue desktop.
    Call this after Chrome has started and has a visible window.
    """
    idx = setup_catalogue_desktop()
    if idx == 0 or not _load():
        return   # no-op if VDA unavailable or only 1 desktop

    hwnds = _find_chrome_hwnds("")
    moved = 0
    for h in hwnds:
        if get_window_desktop(h) != idx:
            if move_window_to_desktop(h, idx):
                moved += 1

    # Switch user BACK to desktop 0 (their main workspace)
    go_to_desktop(0)
    print(f"[vdesk] Moved {moved} Chrome window(s) to desktop {idx}, returned to desktop 0")
