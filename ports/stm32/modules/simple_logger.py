import uos as os
import utime

class SimpleLogger:
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50
    
    def __init__(self, name, log_to_file=False, filename="/sd/logfile.log"):
        self.name = name
        self.level = self.DEBUG
        self.log_to_file = log_to_file
        self.filename = filename
        if self.log_to_file:
            # Ensure the directory exists
            dir_name = "/".join(self.filename.split("/")[:-1])
            if not os.listdir(dir_name):
                os.mkdir(dir_name)

    def set_level(self, level):
        self.level = level

    def _get_timestamp(self):
        now = utime.localtime()
        return "{:04}-{:02}-{:02} {:02}:{:02}:{:02}".format(now[0], now[1], now[2], now[3], now[4], now[5])

    def _log(self, level, msg):
        if level >= self.level:
            timestamp = self._get_timestamp()
            message = f"{timestamp} - {self.name} - {msg}"
            print(message)
            if self.log_to_file:
                self._write_to_file(message)

    def _write_to_file(self, message):
        try:
            with open(self.filename, 'a') as log_file:
                log_file.write(message + "\n")
        except Exception as e:
            print(f"Failed to write to log file: {e}")

    def debug(self, msg):
        self._log(self.DEBUG, f"DEBUG: {msg}")

    def info(self, msg):
        self._log(self.INFO, f"INFO: {msg}")

    def warning(self, msg):
        self._log(self.WARNING, f"WARNING: {msg}")

    def error(self, msg):
        self._log(self.ERROR, f"ERROR: {msg}")

    def critical(self, msg):
        self._log(self.CRITICAL, f"CRITICAL: {msg}")

    def get_logger(self):
        return self
