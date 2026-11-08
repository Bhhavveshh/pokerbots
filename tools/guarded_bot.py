"""Run the bot with audit guards against filesystem mutations and networking.

This is a local diagnostic, not an OS security sandbox or organizer certification.
"""

import os
import sys

sys.dont_write_bytecode = True


def guard(event, args):
    if event == "open":
        flags = args[2] or 0
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            raise PermissionError("runtime filesystem mutation blocked")
    if event.startswith("socket.") or event in ("subprocess.Popen", "os.system"):
        raise PermissionError("runtime network/process operation blocked")
    if event in ("os.mkdir", "os.remove", "os.rename", "os.rmdir", "os.chmod", "os.link", "os.symlink"):
        raise PermissionError("runtime filesystem mutation blocked")


sys.addaudithook(guard)

from pokerbot.protocol import main

main()
