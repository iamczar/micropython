import uasyncio as asyncio
import uos


class FileStorageSensor:
    """
    Periodically reports filesystem free space to Proteus via SimpleLogger system messages.

    Sends a message with message_source "file_storage_sensor" containing:
      {
        "event": "storage-status",
        "path": "/sd" | "/",
        "total_bytes": int,
        "free_bytes": int,
        "used_bytes": int,
        "free_percent": float
      }
    """

    def __init__(self, event_bus=None, logger=None, path: str = "/sd", loop_hz: float = 0.2):
        self.event_bus = event_bus
        self.logger = logger
        self.path_preferred = path
        self.path_fallback = "/"
        # Default: every 5 seconds
        self.interval_s = 1.0 / loop_hz if loop_hz and loop_hz > 0 else 5.0
        # Cleanup delegated to DataLogger; no commands subscribed here

    def _choose_mount(self) -> str:
        try:
            # If preferred path exists and is a mount, use it
            uos.stat(self.path_preferred)
            return self.path_preferred
        except Exception:
            return self.path_fallback

    def _stat_storage(self, path: str) -> tuple[int, int]:
        """Return (total_bytes, free_bytes) for the given mount path."""
        try:
            s = uos.statvfs(path)
            # MicroPython statvfs: (bsize, frsize, blocks, bfree, bavail, files, ffree, favail, flag, namemax)
            block_size = s[0] if len(s) > 0 else 0
            total_blocks = s[2] if len(s) > 2 else 0
            free_blocks = s[3] if len(s) > 3 else 0
            total = block_size * total_blocks
            free = block_size * free_blocks
            return int(total), int(free)
        except Exception as e:
            if self.logger:
                self.logger.error(f"FileStorageSensor: statvfs failed for {path}: {e}")
            return 0, 0


    async def sensor_loop(self):
        while True:
            try:
                path = self._choose_mount()
                total, free = self._stat_storage(path)
                used = total - free if total >= free else 0
                free_percent = (free / total * 100.0) if total > 0 else 0.0
                payload = {
                    "event": "storage-status",
                    "path": path,
                    "total_bytes": int(total),
                    "free_bytes": int(free),
                    "used_bytes": int(used),
                    "free_percent": float(free_percent),
                }
                if self.logger:
                    try:
                        self.logger.send_system_message("file_storage_sensor", payload)
                    except Exception:
                        # Fallback to plain info if structured send fails
                        self.logger.info(f"FileStorageSensor: {payload}")
            except Exception as e:
                if self.logger:
                    self.logger.error(f"FileStorageSensor: loop error: {e}")
            await asyncio.sleep(self.interval_s)


