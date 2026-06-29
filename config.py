import os
from dotenv import load_dotenv

POLL_INTERVAL = 0.1 # how often does the program check what media is playing, lower values improve syching accuracy
WIN_DEBUG_ACTIVE = False # toggles debug in windows.py
PIPELINE_DEBUG_ACTIVE = True #toggles debug in data_cacher.py
CLEAR_PIPELINE_ON_NEW_SONG = False # toggles if pipeline debug is being cleared on a new song

SERVER_MODE = True # toggles pytorch and other AI, only uses already proceeded audio.
                   # if media wasnt proceeded, it is skipped

# SETTINGS BELOW ARE ONLY APPLIED IF SERVER_MODE = TRUE

GLOBAL_OFFSET_SECONDS = 0.0 # 
SNAP_TOLERANCE_RATIO = 0.45 # 
KEEP_PIPELINE_FILES = False # determines if pipeline files (instrumentals, lyrics etc) stay
                            # on the drive after master_sync.json is created
YT_COOKIES_LOCATION = "D:/lyrica/venv/cookies.txt" # path to cookies file, exported from youtube.com (via "Get cookies.txt LOCALLY" plugin)
VISUALISE_LYRICS = False # toggles lyrics display in console after the song has been proceeded by the backend

load_dotenv()

WORKER_SECRET = os.getenv("WORKER_SECRET").strip()
SERVER_URL = os.getenv("SERVER_URL").strip()
DATABASE_URL = os.getenv("DATABASE_URL").strip()
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not set in .env")