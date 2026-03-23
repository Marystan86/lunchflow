from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class UserPublic(BaseModel):
    id: int
    tg_id: int
    full_name: str
    tg_username: str | None = None
    photo_url: str | None = None
    role: str
    status: str


class TelegramAuthRequest(BaseModel):
    initData: str


class AuthResponse(BaseModel):
    token: str
    user: UserPublic


class UserMeUpdate(BaseModel):
    full_name: str | None = None
    photo_url: str | None = None
    city: str | None = None
    company: str | None = None
    position: str | None = None
    industry: str | None = None
    annual_revenue: str | None = None
    employee_count: int | None = None
    core_competencies: str | None = None
    goal_2025: str | None = None
    club_request: str | None = None
    hobbies: str | None = None
    help_offer: str | None = None
    bio: str | None = None
    help_tags: list[str] | None = None
    need_tags: list[str] | None = None
    contacts: dict[str, Any] | None = None
    visibility: Literal["members_only", "hidden", "public"] | None = None


class BadgePreviewItem(BaseModel):
    code: str
    title: str | None = None
    icon: str | None = None
    badge_type: str | None = None


class MemberListItem(UserPublic):
    city: str | None = None
    company: str | None = None
    position: str | None = None
    company_name: str | None = None
    industry: str | None = None
    annual_revenue: str | None = None
    employee_count: int | None = None
    core_competencies: str | None = None
    goal_2025: str | None = None
    club_request: str | None = None
    hobbies: str | None = None
    help_offer: str | None = None
    badges_preview: list[BadgePreviewItem] = Field(default_factory=list)
    help_tags: list[str] = Field(default_factory=list)
    need_tags: list[str] = Field(default_factory=list)


class MemberDetail(MemberListItem):
    bio: str | None = None
    contacts: dict[str, Any] = Field(default_factory=dict)
    visibility: str


class BadgeItem(BaseModel):
    id: int
    code: str
    title: str
    description: str | None = None
    icon: str | None = None
    badge_type: str
    grant_mode: str
    criteria_type: str | None = None
    criteria_value: int | None = None
    vote_threshold: int | None = None
    cooldown_days: int | None = None
    is_active: int
    earned_at: str | None = None


class BadgeVoteRequest(BaseModel):
    to_user_id: int
    badge_code: str
    meeting_id: int
    comment: str | None = None


class BadgeVoteResponse(BaseModel):
    voted: bool
    votes_count: int
    threshold: int
    granted: bool


class NewsPublic(BaseModel):
    id: int
    type: str
    tag: str | None = None
    title: str
    body: str
    media_urls: list[str] = Field(default_factory=list)
    entity_type: str | None = None
    entity_id: int | None = None
    created_by_user_id: int | None = None
    created_at: str
    is_pinned: bool = False


class NewsCreateRequest(BaseModel):
    title: str
    body: str
    tag: str | None = None
    created_at: str | None = None
    media_urls: list[str] | None = None
    is_pinned: bool | None = None


class NewsListResponse(BaseModel):
    items: list[NewsPublic]


class EventCreateRequest(BaseModel):
    title: str
    description: str | None = None
    event_type: str
    city: str | None = None
    location: str | None = None
    capacity: int
    starts_at: str
    category: str | None = None
    tags: list[str] | None = None


class EventPublic(BaseModel):
    id: int
    owner_id: int
    created_by_user_id: int | None = None
    created_by_role: str | None = None
    created_by_name: str | None = None
    created_source: str | None = None
    club_label: str | None = None
    is_club_event: bool | None = None
    title: str
    description: str | None = None
    event_type: str
    city: str | None = None
    location: str | None = None
    capacity: int
    starts_at: str
    status: str
    category: str | None = None
    tags: list[str] | None = None
    created_at: str
    confirmed_at: str | None = None


class MeetingRequestCreate(BaseModel):
    to_user_id: int
    scheduled_for: str
    format: Literal["online", "offline"]
    location: str | None = None
    message: str | None = None
    expires_at: str | None = None


class MeetingRequestApiCreate(BaseModel):
    to_user_id: int
    proposed_time: datetime
    format: Literal["online", "offline"]
    message: str | None = None


class MeetingRequestRespond(BaseModel):
    action: Literal["accept", "decline", "cancel", "expire"]


class MeetingConfirmationCreate(BaseModel):
    confirmation_status: Literal["met", "not_met"]
    comment: str | None = None


class LightningDashboardItem(BaseModel):
    id: int
    title: str
    subtitle: str
    status: str
    scheduled_for: str | None = None
    format: str | None = None
    city: str | None = None
    location: str | None = None
    message: str | None = None
    event_id: int | None = None
    is_club_event: bool | None = None
    registered: int | None = None
    capacity: int | None = None
    category: str | None = None
    created_by_user_id: int | None = None
    created_by_role: str | None = None
    created_by_name: str | None = None
    tags: list[str] | str | None = None


class LightningDashboardResponse(BaseModel):
    outgoing_requests: list[LightningDashboardItem] = Field(default_factory=list)
    incoming_requests: list[LightningDashboardItem] = Field(default_factory=list)
    group_meetings: list[LightningDashboardItem] = Field(default_factory=list)
    club_events: list[LightningDashboardItem] = Field(default_factory=list)
