import json
import os
import requests
import smtplib
import time
from dataclasses import dataclass
from dotenv import load_dotenv
from enum import StrEnum

load_dotenv()

WARNING = 80
CRITICAL = 90

REOLINK_USERNAME = os.getenv("REOLINK_USERNAME", "")
REOLINK_PASSWORD = os.getenv("REOLINK_PASSWORD", "")

SMTP_SERVER = os.getenv("SMTP_SERVER", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "")


def get_email_subscribers():
    email_subscribers = []
    with open("data/emails.txt", "r") as f:
        for line in f:
            if line.strip().startswith("#"):
                continue
            email_subscribers.append(line.strip())
    return email_subscribers


def get_camera_addresses():
    camera_addresses = []
    with open("data/cameras.txt", "r") as f:
        for line in f:
            if line.strip().startswith("#"):
                continue
            camera_addresses.append(line.strip())
    return camera_addresses


class Level(StrEnum):
    OKAY = "OKAY"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class HddData:
    name: str
    available_space: float
    used_space: float

    def __post_init__(self):
        self.available_space = float(self.available_space)
        self.used_space = self.available_space - float(self.used_space)

    def __str__(self):
        available_gb = self.available_space / 1000
        used_gb = self.used_space / 1000
        return f"{self.name}: {used_gb:.2f}GB/{available_gb:.2f}GB ({self.percentage:.2f}%)"

    @property
    def percentage(self):
        return (
            100
            - ((self.available_space - self.used_space) / self.available_space) * 100
        )


def send_email(hdd_data, level: Level):
    try:
        smtp = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        smtp.ehlo()
        smtp.starttls()
        smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
        for email in get_email_subscribers():
            if level == Level.OKAY:
                message = f"Subject: [Reolink Camera] {hdd_data.name} : Storage level is healthy again\n\n Status: {hdd_data}"
            elif level == Level.WARNING:
                message = f"Subject: [Reolink Camera] {hdd_data.name}: Storage level is getting low\n\n Status: {hdd_data}"
            elif level == Level.CRITICAL:
                message = f"Subject: [Reolink Camera] {hdd_data.name}: Storage level is getting critical\n\n Status: {hdd_data}"
            else:
                message = f"Subject: [Reolink Camera] {hdd_data.name}: Storage level is unknown\n\n Something went wrong"
            smtp.sendmail(SMTP_FROM, email, message)
        smtp.quit()
    except Exception as e:
        print(f"Error: {e}")


def get_dev_name(camera_address):
    url = f"{camera_address}/api.cgi?cmd=GetDevName&user={REOLINK_USERNAME}&password={REOLINK_PASSWORD}"
    response = requests.get(url)
    return response.json()[0]["value"]["DevName"]["name"]


def get_hdd_data(camera_address):
    url = f"{camera_address}/api.cgi?cmd=GetHddInfo&user={REOLINK_USERNAME}&password={REOLINK_PASSWORD}"
    response = requests.get(url)
    capacity = response.json()[0]["value"]["HddInfo"][0]["capacity"]
    size = response.json()[0]["value"]["HddInfo"][0]["size"]
    return HddData(
        name=get_dev_name(camera_address),
        available_space=capacity,
        used_space=size,
    )


def update_reolink_cameras():
    with open("data/status.json", "r") as f:
        current_status = json.load(f)
    for camera_address in get_camera_addresses():
        try:
            hdd_data = get_hdd_data(camera_address)
        except Exception as e:
            print(f"Error: {e}")
            continue
        # If the percentage is higher than the warning threshold, but only if the status was previously okay
        if float(current_status.get(hdd_data.name, 0)) < WARNING <= hdd_data.percentage:
            send_email(hdd_data, Level.WARNING)
        # If the percentage is higher than the critical threshold, but only if the status was previously okay or warning
        elif (
            float(current_status.get(hdd_data.name, 0))
            < CRITICAL
            <= hdd_data.percentage
        ):
            send_email(hdd_data, Level.CRITICAL)
        # If the percentage is lower than the warning threshold, but the status was previously critical
        elif (
            float(current_status.get(hdd_data.name, 0)) >= WARNING > hdd_data.percentage
        ):
            send_email(hdd_data, Level.OKAY)

        current_status[hdd_data.name] = hdd_data.percentage
    with open("data/status.json", "w+") as f:
        json.dump(current_status, f, ensure_ascii=False, indent=4)


def create_if_not_exists(path, content="", directory=False):
    if not os.path.exists(path):
        if directory:
            os.makedirs(path)
        else:
            with open(path, "w") as f:
                f.write(content)


create_if_not_exists("data", directory=True)
create_if_not_exists(
    "data/cameras.txt", "# Enter one camera address per line (http(s)://ip:port)"
)
create_if_not_exists("data/emails.txt", "# Enter one email address per line")
create_if_not_exists("data/status.json", "{}")


def loop():
    try:
        update_reolink_cameras()
        time.sleep(600)
        loop()
    except KeyboardInterrupt:
        print("Exiting...")
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(600)
        loop()


if __name__ == "__main__":
    loop()
