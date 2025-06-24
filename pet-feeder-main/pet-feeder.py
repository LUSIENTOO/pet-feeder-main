import sys
import os
import json
import asyncio
from datetime import datetime
from typing import List

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QListWidget, QTimeEdit, QLineEdit, QMessageBox, QInputDialog
)
from PyQt5.QtCore import Qt, QTime, QTimer
from PyQt5.QtGui import QPixmap, QImage

from qasync import QEventLoop, asyncSlot

from viam.robot.client import RobotClient
from viam.components.board import Board
from viam.components.motor import Motor
from viam.components.camera import Camera

# --- Viam Credentials and Component Names ---
ROBOT_API_KEY = "az50dxbw0ddyuzl8ulb7osjxiavaexiy"
ROBOT_API_KEY_ID = "42efaa5a-fa77-4bc1-8bc3-91cf494d1584"
ROBOT_ADDRESS = "petfeeder-main.o8s889lyi5.viam.cloud"
STEPPER_NAME = "stepper"
BOARD_NAME = "pi"
CAMERA_NAME = "petcam"

# --- Default Schedule (HH:MM 24h format) ---
DEFAULT_SCHEDULE = ["06:00", "12:00", "16:02"]
SCHEDULE_FILE = "schedule.json"

class PetFeederApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pet Feeder Controller")
        self.setGeometry(200, 200, 500, 600)
        self.robot = None
        self.stepper = None
        self.camera = None
        self.schedule: List[str] = self.load_schedule()
        self.last_feed_time = None
        self.init_ui()
        self.loop = asyncio.get_event_loop()
        self.connected = False
        
        # Schedule timer - check every 30 seconds
        self.schedule_timer = QTimer()
        self.schedule_timer.timeout.connect(self.check_schedule)
        self.schedule_timer.start(30000)  # 30 seconds

        # Camera timer - refresh every second
        self.camera_timer = QTimer()
        self.camera_timer.timeout.connect(self.refresh_camera_auto)
        self.camera_timer.start(1000)  # 1 second

    def load_schedule(self):
        if os.path.exists(SCHEDULE_FILE):
            try:
                with open(SCHEDULE_FILE, "r") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
            except Exception as e:
                print(f"[SCHEDULE] Failed to load schedule: {e}")
        return DEFAULT_SCHEDULE.copy()

    def save_schedule(self):
        try:
            with open(SCHEDULE_FILE, "w") as f:
                json.dump(self.schedule, f)
        except Exception as e:
            print(f"[SCHEDULE] Failed to save schedule: {e}")

    def init_ui(self):
        layout = QVBoxLayout()
        # Status
        self.status_label = QLabel("Status: Not connected")
        layout.addWidget(self.status_label)
        # Connect button
        self.connect_btn = QPushButton("Connect to Robot")
        self.connect_btn.clicked.connect(self.on_connect)
        layout.addWidget(self.connect_btn)
        # Schedule
        layout.addWidget(QLabel("Feeding Schedule (HH:MM):"))
        self.schedule_list = QListWidget()
        self.schedule_list.addItems(self.schedule)
        layout.addWidget(self.schedule_list)
        sch_btns = QHBoxLayout()
        self.add_time_btn = QPushButton("Add Time")
        self.add_time_btn.clicked.connect(self.add_time)
        sch_btns.addWidget(self.add_time_btn)
        self.remove_time_btn = QPushButton("Remove Selected")
        self.remove_time_btn.clicked.connect(self.remove_time)
        sch_btns.addWidget(self.remove_time_btn)
        layout.addLayout(sch_btns)
        # Manual Feed
        self.feed_btn = QPushButton("Feed Now")
        self.feed_btn.clicked.connect(self.on_feed)
        self.feed_btn.setEnabled(False)
        layout.addWidget(self.feed_btn)
        # Camera
        layout.addWidget(QLabel("Live Camera:"))
        self.camera_label = QLabel()
        self.camera_label.setFixedSize(400, 300)
        self.camera_label.setStyleSheet("background: #222;")
        layout.addWidget(self.camera_label)
        self.refresh_cam_btn = QPushButton("Refresh Camera")
        self.refresh_cam_btn.clicked.connect(self.on_refresh_camera)
        self.refresh_cam_btn.setEnabled(False)
        layout.addWidget(self.refresh_cam_btn)
        self.setLayout(layout)

    @asyncSlot()
    async def on_connect(self):
        self.status_label.setText("Status: Connecting...")
        self.connect_btn.setEnabled(False)
        try:
            opts = RobotClient.Options.with_api_key(
                api_key=ROBOT_API_KEY,
                api_key_id=ROBOT_API_KEY_ID
            )
            self.robot = await RobotClient.at_address(ROBOT_ADDRESS, opts)
            print("Available components:", self.robot.resource_names)
            self.stepper = Motor.from_robot(self.robot, STEPPER_NAME)
            self.camera = Camera.from_robot(self.robot, CAMERA_NAME)
            self.connected = True
            self.status_label.setText("Status: Connected!")
            self.feed_btn.setEnabled(True)
            self.refresh_cam_btn.setEnabled(True)
        except Exception as e:
            self.status_label.setText(f"Status: Connection failed")
            QMessageBox.critical(self, "Connection Error", str(e))
            self.connect_btn.setEnabled(True)

    def add_time(self):
        time, ok = QInputDialog.getText(self, "Add Feeding Time", "Enter time (HH:MM):")
        if ok and time:
            try:
                datetime.strptime(time, "%H:%M")
                if time not in self.schedule:
                    self.schedule.append(time)
                    self.schedule.sort()
                    self.schedule_list.clear()
                    self.schedule_list.addItems(self.schedule)
                    self.save_schedule()
            except ValueError:
                QMessageBox.warning(self, "Invalid Time", "Please enter time in HH:MM format.")

    def remove_time(self):
        selected = self.schedule_list.currentRow()
        if selected >= 0:
            self.schedule.pop(selected)
            self.schedule_list.takeItem(selected)
            self.save_schedule()

    def check_schedule(self):
        """Check if it's time to feed based on the schedule"""
        if not self.connected or not self.stepper:
            return
            
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        
        # Check if current time matches any schedule time
        if current_time in self.schedule:
            # Prevent multiple feeds at the same time
            if self.last_feed_time != current_time:
                self.last_feed_time = current_time
                print(f"[SCHEDULE] Time to feed! Current time: {current_time}")
                # Trigger feeding asynchronously
                asyncio.create_task(self.scheduled_feed())

    @asyncSlot()
    async def scheduled_feed(self):
        """Perform a scheduled feed"""
        if not self.connected or not self.stepper:
            return
            
        self.status_label.setText("Status: Scheduled feeding...")
        try:
            print("[SCHEDULE] Scheduled feeding started")
            await self.stepper.go_for(rpm=500, revolutions=-3)
            await self.stepper.stop()
            self.status_label.setText("Status: Scheduled feed complete!")
            print("[SCHEDULE] Scheduled feeding complete")
        except Exception as e:
            print(f"[SCHEDULE] Scheduled feed error: {e}")
            self.status_label.setText("Status: Scheduled feed failed!")

    @asyncSlot()
    async def on_feed(self):
        if not self.connected or not self.stepper:
            QMessageBox.warning(self, "Not Connected", "Connect to the robot first.")
            return
        self.feed_btn.setEnabled(False)
        self.status_label.setText("Status: Feeding...")
        try:
            print("[DEBUG] Feeding started")
            await self.stepper.go_for(rpm=500, revolutions=-3)
            await self.stepper.stop()
            self.status_label.setText("Status: Feed complete!")
            print("[DEBUG] Feeding complete")
        except Exception as e:
            print(f"[DEBUG] Feed error: {e}")
            QMessageBox.critical(self, "Feed Error", str(e))
            self.status_label.setText("Status: Feed failed!")
        finally:
            print("[DEBUG] Re-enabling feed button")
            self.feed_btn.setEnabled(True)

    @asyncSlot()
    async def on_refresh_camera(self):
        await self._refresh_camera()

    def refresh_camera_auto(self):
        if self.connected and self.camera:
            asyncio.create_task(self._refresh_camera(auto=True))

    async def _refresh_camera(self, auto=False):
        self.refresh_cam_btn.setEnabled(False)
        if not self.connected or not self.camera:
            if not auto:
                QMessageBox.warning(self, "Not Connected", "Connect to the robot first.")
            self.refresh_cam_btn.setEnabled(True)
            return
        if not auto:
            self.status_label.setText("Status: Fetching camera...")
        try:
            viam_img = await self.camera.get_image(mime_type="image/jpeg")
            # Handle ViamImage object properly
            if hasattr(viam_img, 'data'):
                img_bytes = viam_img.data
            else:
                img_bytes = viam_img
            qimg = QImage.fromData(img_bytes, "JPEG")
            pixmap = QPixmap.fromImage(qimg)
            pixmap = pixmap.scaled(self.camera_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.camera_label.setPixmap(pixmap)
            if not auto:
                self.status_label.setText("Status: Camera updated!")
        except Exception as e:
            if not auto:
                QMessageBox.critical(self, "Camera Error", str(e))
                self.status_label.setText("Status: Camera failed!")
        finally:
            self.refresh_cam_btn.setEnabled(True)


def main():
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    window = PetFeederApp()
    window.show()
    with loop:
        loop.run_forever()

if __name__ == "__main__":
    main()