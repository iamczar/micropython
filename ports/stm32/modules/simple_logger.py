import uos as os
import utime
import json

class SimpleLogger:
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50
    
    def __init__(self, name, module_id=None, log_to_file=False, filename="/sd/logfile.log"):
        self.name = name
        self.module_id = module_id
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

    def _get_level_name(self, level):
        """Convert level number to name"""
        if level == self.DEBUG:
            return "DEBUG"
        elif level == self.INFO:
            return "INFO"
        elif level == self.WARNING:
            return "WARNING"
        elif level == self.ERROR:
            return "ERROR"
        elif level == self.CRITICAL:
            return "CRITICAL"
        else:
            return "UNKNOWN"

    def _log(self, level, msg):
        if level >= self.level:
            timestamp = self._get_timestamp()
            message = f"{timestamp} - {self.name} - {msg}"
            
            # Create JSON log message
            log_json = {
                "message_source": self.name,
                "module_id": self.module_id,
                "timestamp": timestamp,
                "level": self._get_level_name(level),
                "message": msg
            }
            
            # Only print to console if not logging to file (to avoid USB_VCP spam)
            if not self.log_to_file:
                print(json.dumps(log_json))
            if self.log_to_file:
                self._write_to_file(message)

    def send_system_message(self, message_source, msg=None):
        """
        Send a system message via serial (USB_VCP)
        
        Args:
            message_source (str): Name of the internal module sending the message
            msg (dict, optional): Message content as a dictionary
        """
        timestamp = self._get_timestamp()
        
        system_json = {
            "message_source": message_source,
            "module_id": self.module_id,
            "timestamp": timestamp
        }
        
        # Add message content if provided
        if msg is not None:
            system_json["message"] = msg
                   
        print(json.dumps(system_json))

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
