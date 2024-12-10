# config.py
import json

class Config:
    def __init__(self, config_file_path):
        self.config_file_path = config_file_path
        self.config_data = None
        self.load_config()

    def load_config(self):
        """Load the configuration from a JSON file."""
        try:
            with open(self.config_file_path, 'r') as file:
                self.config_data = json.load(file)
        except OSError:
            print(f"Config file {self.config_file_path} not found.")
        except ValueError:
            print(f"Error decoding JSON from {self.config_file_path}.")

    def get_config(self, name):
        """Retrieve the configuration for a specific component by name."""
        if self.config_data is None:
            raise Exception("Config data is not loaded")
        return self.config_data.get(name, None)
