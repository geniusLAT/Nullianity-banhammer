import json


class settings:
    def load_settings(self, file_path):
        with open(file_path, "r") as file:
            settings = json.load(file)
        return settings

    def __init__(self):
        settings_file = "src/settings.json"
        settings = self.load_settings(settings_file)

        self.logger_chat = settings["logger_chat"]
        self.special_chat = settings["special_chat"]
        self.appeal_channel = settings["appeal_channel"]
        self.appeal_channel_discussion = settings["appeal_channel_discussion"]
        self.token = settings["token"]
        self.toxicity_threshold = settings["toxicity_threshold"]

        self.databasename = settings["databasename"]
        self.databaseUsername = settings["databaseUsername"]
        self.databasePassword = settings["databasePassword"]
        self.databaseIp = settings["databaseIp"]
        self.databasePort = settings["databasePort"]


if __name__ == "__main__":
    my_settings = settings()

    print(f"Logger Chat ID: {my_settings.logger_chat}")
    print(f"Special Chat ID: {my_settings.special_chat}")
    print(f"Appeal channel ID: {my_settings.appeal_channel}")
    print(f"Appeal channel discussion chat ID: {my_settings.appeal_channel_discussion}")
    print(f"Token: {my_settings.token}")
    print(f"Toxicity Threshold: {my_settings.toxicity_threshold}")

    print(f"databasename: {my_settings.databasename}")
    print(f"databaseUsername: {my_settings.databaseUsername}")
    print(f"databasePassword: {my_settings.databasePassword}")
    print(f"databaseIp: {my_settings.databaseIp}")
    print(f"databasePort: {my_settings.databasePort}")
