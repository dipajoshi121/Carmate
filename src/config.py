from dataclasses import dataclass

@dataclass
class Config:
    API_BASE: str = "http://localhost:4000"

CFG = Config()
