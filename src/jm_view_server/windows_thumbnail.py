"""Windows Shell thumbnail extraction, isolated from the web server process."""

import ctypes
import io
import json
import os
import subprocess
import sys
import uuid

VIDEO_EXTENSIONS = frozenset({
    '.mp4', '.m4v', '.mkv', '.avi', '.mov', '.wmv', '.webm', '.flv',
    '.mpeg', '.mpg', '.ts', '.mts', '.m2ts', '.3gp', '.ogv',
})


def is_video_file(path):
    return os.path.splitext(path)[1].lower() in VIDEO_EXTENSIONS


def extract_thumbnail(path, width, height, timeout=6):
    """A hung third-party codec is killed after the bounded extraction timeout."""
    if os.name != 'nt' or not is_video_file(path):
        return None
    try:
        result = subprocess.run(
            [sys.executable, '-B', os.path.abspath(__file__)],
            input=json.dumps([path, width, height]).encode('utf-8'),
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode == 0 and result.stdout.startswith(b'\x89PNG\r\n\x1a\n'):
            if len(result.stdout) <= 2 * 1024 * 1024:
                return result.stdout
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def _shell_thumbnail(path, width, height):
    from ctypes import wintypes
    from PIL import Image

    class GUID(ctypes.Structure):
        _fields_ = [('data', ctypes.c_ubyte * 16)]

    class BitmapInfoHeader(ctypes.Structure):
        _fields_ = [
            ('size', wintypes.DWORD), ('width', wintypes.LONG),
            ('height', wintypes.LONG), ('planes', wintypes.WORD),
            ('bit_count', wintypes.WORD), ('compression', wintypes.DWORD),
            ('size_image', wintypes.DWORD), ('x_pixels', wintypes.LONG),
            ('y_pixels', wintypes.LONG), ('colors_used', wintypes.DWORD),
            ('colors_important', wintypes.DWORD),
        ]

    class BitmapInfo(ctypes.Structure):
        _fields_ = [('header', BitmapInfoHeader), ('colors', wintypes.DWORD * 3)]

    class Bitmap(ctypes.Structure):
        _fields_ = [
            ('type', wintypes.LONG), ('width', wintypes.LONG),
            ('height', wintypes.LONG), ('width_bytes', wintypes.LONG),
            ('planes', wintypes.WORD), ('bits_pixel', wintypes.WORD),
            ('bits', ctypes.c_void_p),
        ]

    ole = ctypes.WinDLL('ole32')
    shell = ctypes.WinDLL('shell32')
    gdi = ctypes.WinDLL('gdi32')
    ole.CoInitializeEx.argtypes = [ctypes.c_void_p, wintypes.DWORD]
    ole.CoInitializeEx.restype = wintypes.LONG
    ole.CoUninitialize.argtypes = []
    shell.SHCreateItemFromParsingName.argtypes = [
        wintypes.LPCWSTR, ctypes.c_void_p, ctypes.POINTER(GUID),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    shell.SHCreateItemFromParsingName.restype = wintypes.LONG
    gdi.DeleteObject.argtypes = [ctypes.c_void_p]
    gdi.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
    gdi.CreateCompatibleDC.restype = ctypes.c_void_p
    gdi.DeleteDC.argtypes = [ctypes.c_void_p]
    gdi.GetObjectW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
    gdi.GetDIBits.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT,
                            wintypes.UINT, ctypes.c_void_p,
                            ctypes.POINTER(BitmapInfo), wintypes.UINT]

    if ole.CoInitializeEx(None, 2) < 0:  # Apartment-threaded Shell handler.
        return None
    factory = ctypes.c_void_p()
    bitmap = ctypes.c_void_p()
    dc = None
    try:
        iid = GUID((ctypes.c_ubyte * 16).from_buffer_copy(
            uuid.UUID('bcc18b79-ba16-442f-80c4-8a59c30c463b').bytes_le))
        if shell.SHCreateItemFromParsingName(path, None, ctypes.byref(iid),
                                           ctypes.byref(factory)) < 0:
            return None
        vtable = ctypes.cast(factory, ctypes.POINTER(
            ctypes.POINTER(ctypes.c_void_p))).contents
        get_image = ctypes.WINFUNCTYPE(
            wintypes.LONG, ctypes.c_void_p, wintypes.SIZE, wintypes.DWORD,
            ctypes.POINTER(ctypes.c_void_p))(vtable[3])
        # THUMBNAILONLY: never mistake a file-type icon for a video preview.
        if get_image(factory, wintypes.SIZE(width, height), 0x8,
                     ctypes.byref(bitmap)) < 0:
            return None
        info = Bitmap()
        if not gdi.GetObjectW(bitmap, ctypes.sizeof(info), ctypes.byref(info)):
            return None
        w, h = info.width, abs(info.height)
        if not (0 < w <= 512 and 0 < h <= 512):
            return None
        dib = BitmapInfo()
        dib.header.size = ctypes.sizeof(BitmapInfoHeader)
        dib.header.width, dib.header.height = w, -h
        dib.header.planes, dib.header.bit_count = 1, 32
        pixels = ctypes.create_string_buffer(w * h * 4)
        dc = gdi.CreateCompatibleDC(None)
        if not dc or gdi.GetDIBits(dc, bitmap, 0, h, pixels,
                                 ctypes.byref(dib), 0) != h:
            return None
        image = Image.frombytes('RGB', (w, h), pixels.raw, 'raw', 'BGRX')
        image.thumbnail((width, height), Image.Resampling.LANCZOS)
        output = io.BytesIO()
        image.save(output, format='PNG')
        return output.getvalue()
    finally:
        if dc:
            gdi.DeleteDC(dc)
        if bitmap.value:
            gdi.DeleteObject(bitmap)
        if factory.value:
            vtable = ctypes.cast(factory, ctypes.POINTER(
                ctypes.POINTER(ctypes.c_void_p))).contents
            ctypes.WINFUNCTYPE(wintypes.ULONG, ctypes.c_void_p)(vtable[2])(factory)
        ole.CoUninitialize()


if __name__ == '__main__':
    try:
        path, width, height = json.loads(sys.stdin.buffer.read(65536))
        if os.name != 'nt' or not is_video_file(path):
            raise ValueError('Unsupported thumbnail')
        data = _shell_thumbnail(os.path.abspath(path),
                                max(1, min(512, int(width))),
                                max(1, min(512, int(height))))
        if not data:
            sys.exit(1)
        sys.stdout.buffer.write(data)
    except Exception:
        sys.exit(1)
