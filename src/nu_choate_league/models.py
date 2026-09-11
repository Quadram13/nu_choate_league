from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class Platform(StrEnum):
    ESPN = "espn"
    SLEEPER = "sleeper"


class Season(BaseModel):
    year: int
    platform: Platform
    league_id: str
    name: str
    vs_median: bool = False

    @field_validator("league_id", mode="before")
    @classmethod
    def league_id_str(cls, value: object) -> str:
        return str(value)


class Manager(BaseModel):
    id: str
    display_name: str
    espn_member_ids: list[str] = Field(default_factory=list)
    sleeper_user_ids: list[str] = Field(default_factory=list)

    @field_validator("espn_member_ids", "sleeper_user_ids", mode="before")
    @classmethod
    def empty_none(cls, value: object) -> object:
        return [] if value is None else value


class DumpOwner(BaseModel):
    year: int
    platform: Platform
    platform_id: str
    label: str


class DumpPlayer(BaseModel):
    platform: Platform
    platform_id: str
    display_name: str = ""
    position: str | None = None
    years: list[int] = Field(default_factory=list)


class Player(BaseModel):
    id: str
    display_name: str
    sleeper_id: str | None = None
    espn_id: int | None = None
    position: str | None = None
    source: str = "sleeper"


class LineupSlot(BaseModel):
    player_id: str
    player_name: str
    slot: str
    points: float
    started: bool


class MatchupSide(BaseModel):
    manager_id: str | None = None
    team_name: str
    platform_team_id: str | None = None
    points: float
    lineup: list[LineupSlot] = Field(default_factory=list)


class Matchup(BaseModel):
    id: str
    year: int
    week: int
    kind: str
    home: MatchupSide
    away: MatchupSide


class TeamSeason(BaseModel):
    manager_id: str
    team_name: str
    platform_team_id: str
    wins: int = 0
    losses: int = 0
    ties: int = 0
    points_for: float = 0.0
    points_against: float = 0.0
    playoff_seed: int | None = None
    final_rank: int | None = None


class OfficialRecord(BaseModel):
    manager_id: str
    wins: int
    losses: int
    ties: int
    points_for: float


class DraftPick(BaseModel):
    year: int
    round: int
    overall: int
    manager_id: str
    player_id: str
    player_name: str
    keeper: bool = False


class PlayerMove(BaseModel):
    player_id: str
    player_name: str
    manager_id: str


class Transaction(BaseModel):
    id: str
    year: int
    week: int
    type: str
    status: str
    at: int | None = None
    seq: int | None = None
    priority: int | None = None
    bid: int | None = None
    note: str | None = None
    adds: list[PlayerMove] = Field(default_factory=list)
    drops: list[PlayerMove] = Field(default_factory=list)


class WeekScore(BaseModel):
    week: int
    manager_id: str
    points: float
    paired: bool = True


class PlayerWeek(BaseModel):
    year: int
    week: int
    player_id: str
    player_name: str
    position: str | None = None
    points: float
    rostered: bool = False
    started: bool = False
    manager_id: str | None = None


class PlayoffRound(BaseModel):
    name: str
    week: int
    byes: int = 0


class PlayoffFormat(BaseModel):
    teams: int = 0
    byes: int = 0
    start_week: int | None = None
    rounds: list[PlayoffRound] = Field(default_factory=list)


class SeasonOutcome(BaseModel):
    year: int
    champion: str | None = None
    runner_up: str | None = None
    regular_season_champion: str | None = None
    most_points: str | None = None
    playoff_managers: list[str] = Field(default_factory=list)
    playoff_format: PlayoffFormat | None = None


class CareerSeason(BaseModel):
    year: int
    team_name: str
    wins: int
    losses: int
    ties: int
    points_for: float
    points_against: float
    regular_season_rank: int | None = None
    playoff: bool = False
    champion: bool = False
    runner_up: bool = False
    regular_season_champion: bool = False
    most_points: bool = False


class CareerRecord(BaseModel):
    manager_id: str
    seasons: int = 0
    wins: int = 0
    losses: int = 0
    ties: int = 0
    points_for: float = 0.0
    points_against: float = 0.0
    titles: int = 0
    runner_up: int = 0
    playoff_appearances: int = 0
    regular_season_titles: int = 0
    most_points_titles: int = 0
    years: list[CareerSeason] = Field(default_factory=list)


class HeadToHeadSide(BaseModel):
    wins: int = 0
    losses: int = 0
    ties: int = 0
    points_for: float = 0.0
    points_against: float = 0.0
    games: int = 0


class HeadToHeadPair(BaseModel):
    left: str
    right: str
    regular: HeadToHeadSide = Field(default_factory=HeadToHeadSide)
    playoff: HeadToHeadSide = Field(default_factory=HeadToHeadSide)


class AlternateSide(BaseModel):
    manager_id: str
    seed: int
    points: float


class AlternateGame(BaseModel):
    home: AlternateSide
    away: AlternateSide
    winner: str | None = None
    tiebreak: str | None = None


class AlternateRound(BaseModel):
    name: str
    week: int
    byes: list[str] = Field(default_factory=list)
    games: list[AlternateGame] = Field(default_factory=list)


class AlternateUniverse(BaseModel):
    id: str
    label: str
    teams: list[TeamSeason] = Field(default_factory=list)
    champion: str | None = None
    runner_up: str | None = None
    regular_season_champion: str | None = None
    playoff_managers: list[str] = Field(default_factory=list)
    bracket: list[AlternateRound] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    matches_official: bool = False


class AlternateSeason(BaseModel):
    year: int
    official_champion: str | None = None
    official_runner_up: str | None = None
    official_regular_season_champion: str | None = None
    universes: list[AlternateUniverse] = Field(default_factory=list)


class SeasonBundle(BaseModel):
    season: Season
    teams: list[TeamSeason]
    matchups: list[Matchup]
    official: list[OfficialRecord]
    draft_picks: list[DraftPick] = Field(default_factory=list)
    transactions: list[Transaction] = Field(default_factory=list)
    through_week: int | None = None
    outcome: SeasonOutcome | None = None
    week_scores: list[WeekScore] = Field(default_factory=list)
    player_weeks: list[PlayerWeek] = Field(default_factory=list)
