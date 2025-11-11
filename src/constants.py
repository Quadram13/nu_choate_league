"""Constants for league settings and position definitions."""

# Default league settings
DEFAULT_PLAYOFF_WEEK_START = 15
DEFAULT_LAST_SCORED_LEG = 17

# Fantasy positions
POSITION_QB = 'QB'
POSITION_RB = 'RB'
POSITION_WR = 'WR'
POSITION_TE = 'TE'
POSITION_K = 'K'
POSITION_DEF = 'DEF'
POSITION_FLEX = 'FLEX'
POSITION_BN = 'BN'  # Bench

# Flex-eligible positions
FLEX_ELIGIBLE_POSITIONS = [POSITION_TE, POSITION_RB, POSITION_WR]

# API Configuration
SLEEPER_API_BASE_URL = 'https://api.sleeper.app/v1'
SLEEPER_PLAYERS_URL = f'{SLEEPER_API_BASE_URL}/players/nfl'

# Application constants
GOAT = 7  # Tom Brady's Super Bowl rings (used for confirmation)

# Data directory paths
DATA_DIR = 'src/data'
MUNGED_DIR = f'{DATA_DIR}/munged'
UNMUNGED_DIR = f'{DATA_DIR}/unmunged'
REPORTS_DIR = f'{DATA_DIR}/reports'

