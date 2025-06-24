# Pet Feeder Desktop App

A PyQt5 desktop application to control your Viam-powered pet feeder robot. Features include:
- Manual and scheduled feeding
- Real-time camera feed
- Persistent, editable feeding schedule

## Features
- **Manual Feed:** Instantly trigger a feeding.
- **Scheduled Feed:** Set custom feeding times; the app will feed automatically at those times.
- **Live Camera:** View a real-time camera feed from your robot.
- **Schedule Persistence:** Your schedule is saved and loaded automatically.

## Setup

1. **Clone the repository** (if you haven't already):
   ```bash
   git clone https://github.com/ZACHARY2215/pet-feeder.git
   cd pet-feeder/pet_feeder_app
   ```

2. **Create and activate a virtual environment (recommended):**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure your Viam credentials:**
   - Edit `pet-feeder.py` and update the following variables with your robot's info:
     ```python
     ROBOT_API_KEY = "your_api_key"
     ROBOT_API_KEY_ID = "your_api_key_id"
     ROBOT_ADDRESS = "your_robot_address"
     STEPPER_NAME = "your_motor_name"
     CAMERA_NAME = "your_camera_name"
     ```

## Usage

1. **Run the app:**
   ```bash
   python pet-feeder.py
   ```
2. **Connect to your robot** by clicking "Connect to Robot".
3. **Add or remove feeding times** as needed. The schedule is saved automatically.
4. **Manual Feed:** Click "Feed Now" to trigger a feed.
5. **Live Camera:** The camera feed updates every second. You can also click "Refresh Camera" for a manual update.

## Notes
- The schedule is saved in `schedule.json` in the app directory.
- Make sure your robot is online and the component names match exactly.
- For troubleshooting, check the terminal for debug output.

## License
MIT
