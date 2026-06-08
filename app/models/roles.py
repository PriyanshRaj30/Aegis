from enum import Enum

class Role(str, Enum):

    ADMIN = "ADMIN"

    DEVELOPER = "DEVELOPER"

    VIEWER = "VIEWER"