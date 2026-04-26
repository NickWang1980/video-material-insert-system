from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


RoleStrategy = Literal["auto", "primary-first", "manual-sequence"]


class RoleConfig(BaseModel):
    id: str
    name: str
    color: str
    isPrimary: bool = False


class RoleAsset(BaseModel):
    id: str
    roleId: str
    fileName: str
    filePath: str
    duration: float
    width: int
    height: int
    asrStatus: str = "pending"
    asrProgress: int = 0
    asrError: str | None = None
    asrSrtPath: str | None = None
    asrStartSeconds: float = 0.0
    asrEndSeconds: float = 0.0
    asrDuration: float = 0.0
    matchedChars: int = 0
    srtTotalChars: int = 0
    unmatchedChars: int = 0
    matchPercent: float = 0.0
    errorPercent: float = 100.0
    manualGatePassed: bool = False
    gatePassed: bool = False


class CompareAssetItem(BaseModel):
    assetId: str
    fileName: str
    asrText: str
    asrStartSeconds: float = 0.0
    asrEndSeconds: float = 0.0
    asrDuration: float = 0.0
    matchedChars: int = 0
    srtTotalChars: int = 0
    unmatchedChars: int = 0
    matchPercent: float = 0.0
    errorPercent: float = 100.0
    manualGatePassed: bool = False
    gatePassed: bool = False
    asrStatus: str = "pending"
    asrProgress: int = 0
    asrError: str | None = None


class CompareRoleSummary(BaseModel):
    matchedChars: int = 0
    srtTotalChars: int = 0
    unmatchedChars: int = 0
    matchPercent: float = 0.0
    errorPercent: float = 100.0
    gatePassed: bool = False
    asrStatus: str = "pending"
    asrProgress: int = 0
    asrError: str | None = None


class CompareRoleItem(BaseModel):
    roleId: str
    roleName: str
    mainText: str
    asrText: str
    matchedChars: int = 0
    srtTotalChars: int = 0
    unmatchedChars: int = 0
    matchPercent: float = 0.0
    errorPercent: float = 100.0
    manualGatePassed: bool = False
    gatePassed: bool = False
    asrStatus: str = "pending"
    asrProgress: int = 0
    asrError: str | None = None
    roleSummary: CompareRoleSummary | None = None
    assets: list[CompareAssetItem] = Field(default_factory=list)


class CompareProjectResponse(BaseModel):
    projectId: int
    projectTitle: str
    roles: list[CompareRoleItem] = Field(default_factory=list)


class SentenceItem(BaseModel):
    id: str
    index: int
    text: str
    roleId: str | None = None
    estimatedDuration: float
    locked: bool = False
    clipId: str | None = None


class TimelineClip(BaseModel):
    id: str
    sentenceId: str
    roleId: str
    assetId: str
    filePath: str
    sourceStart: float
    sourceEnd: float
    duration: float
    timelineStart: float
    timelineEnd: float
    subtitleText: str
    looped: bool = False


class RenderSettings(BaseModel):
    aspectRatio: Literal["9:16", "16:9", "1:1"] = "9:16"
    resolution: Literal["720p", "1080p"] = "1080p"
    fps: Literal[25, 30] = 30
    audioMode: Literal["keep", "mute", "tts"] = "keep"
    subtitleMode: Literal["off", "srt", "burn"] = "off"
    transitionMode: Literal["none", "fade"] = "none"
    roleStrategy: RoleStrategy = "primary-first"
    manualSequence: str | None = None
    primaryRoleId: str = "A"


class RoughCutProjectResponse(BaseModel):
    id: int
    title: str
    script: str
    scriptFileName: str | None = None
    sentences: list[SentenceItem]
    roles: list[RoleConfig]
    roleCount: int = 0
    assets: list[RoleAsset]
    assetCount: int = 0
    settings: RenderSettings
    timeline: list[TimelineClip]
    status: Literal["idle", "processing", "ready", "error"]
    progress: int = 0
    pipelineProgress: int = 0
    rolesAsrProgress: list[dict] = Field(default_factory=list)
    roughCutEnabled: bool = False
    roughCutEnabledReason: str | None = None
    minimumMatchPercent: float = 0.0
    phase: str | None = None
    error: str | None = None
    log: str = ""
    previewUrl: str | None = None
    outputUrl: str | None = None
    stageSummary: str | None = None
    createdAt: datetime
    updatedAt: datetime


class CreateProjectRequest(BaseModel):
    title: str = "混剪项目"
    script: str = ""
    scriptFileName: str | None = None


class UpdateScriptRequest(BaseModel):
    script: str


class UpdateProjectRequest(BaseModel):
    title: str | None = None
    script: str | None = None
    scriptFileName: str | None = None


class SplitScriptRequest(BaseModel):
    script: str | None = None


class AssignRolesRequest(BaseModel):
    strategy: RoleStrategy = "primary-first"
    manualSequence: str | None = None
    primaryRoleId: str = "A"


class UpdateSettingsRequest(BaseModel):
    settings: RenderSettings


class BuildTimelineRequest(BaseModel):
    recalculateDurations: bool = True


class UpdateSentenceRequest(BaseModel):
    roleId: str | None = None
    estimatedDuration: float | None = None
    locked: bool | None = None
    sourceStart: float | None = None
    sourceEnd: float | None = None


class UpdateAssetManualGateRequest(BaseModel):
    manualPassed: bool = False


class ExportRequest(BaseModel):
    mode: Literal["preview", "final"] = "preview"


class StatusResponse(BaseModel):
    status: Literal["idle", "processing", "ready", "error"]
    progress: int
    pipelineProgress: int = 0
    rolesAsrProgress: list[dict] = Field(default_factory=list)
    roughCutEnabled: bool = False
    roughCutEnabledReason: str | None = None
    phase: str | None = None
    error: str | None = None
    previewUrl: str | None = None
    outputUrl: str | None = None
    log: str = ""


class FfmpegStatusResponse(BaseModel):
    status: Literal["clear", "blocked"] = "clear"
    runningCount: int = 0
    runningProjectIds: list[int] = Field(default_factory=list)
    blockedProjectIds: list[int] = Field(default_factory=list)


class ListProjectsResponse(BaseModel):
    items: list[RoughCutProjectResponse] = Field(default_factory=list)
    total: int = 0
