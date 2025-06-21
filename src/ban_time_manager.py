import json


class UserTracker:
    def __init__(self, filename):
        self.filename = filename
        self.data = self.load_data()

    def load_data(self):
        try:
            with open(self.filename, "r") as file:
                data = json.load(file)
                print(data)
                return data
        except FileNotFoundError:
            return {}

    def save_data(self):
        with open(self.filename, "w") as file:
            json.dump(self.data, file)

    def update_user(self, user_id, days):
        self.data[str(user_id)] = days
        self.save_data()

    def get_user_days(self, user_id):
        return self.data.get(str(user_id), 0)
