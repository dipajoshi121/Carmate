import os

class Config:
    API_BASE = os.environ.get("API_BASE", "http://localhost:4000")

CFG = Config()
