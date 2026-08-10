from enum import Enum

class Team(str, Enum):
    SRE = "SRE"
    PLATFORM = "PLATFORM"
    BACKEND = "BACKEND"
    FRONTEND = "FRONTEND"
    DBA = "DBA"
    SECURITY = "SECURITY"
    NETWORK = "NETWORK"
    ON_CALL = "ON_CALL"
