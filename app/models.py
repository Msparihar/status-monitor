from pydantic import BaseModel


class PageInfo(BaseModel):
    id: str
    status_indicator: str | None = None
    status_description: str | None = None


class ComponentUpdate(BaseModel):
    created_at: str
    new_status: str
    old_status: str
    id: str
    component_id: str


class Component(BaseModel):
    created_at: str
    id: str
    name: str
    status: str


class IncidentUpdate(BaseModel):
    body: str | None = None
    created_at: str
    display_at: str | None = None
    id: str
    incident_id: str
    status: str
    updated_at: str | None = None


class Incident(BaseModel):
    backfilled: bool | None = None
    created_at: str
    id: str
    impact: str | None = None
    name: str
    resolved_at: str | None = None
    status: str
    updated_at: str | None = None
    incident_updates: list[IncidentUpdate] = []
    components: list[Component] = []


class ScheduledMaintenance(BaseModel):
    created_at: str
    id: str
    impact: str | None = None
    name: str
    scheduled_for: str | None = None
    scheduled_until: str | None = None
    status: str
    updated_at: str | None = None
    incident_updates: list[IncidentUpdate] = []
    components: list[Component] = []


class Meta(BaseModel):
    unsubscribe: str | None = None
    documentation: str | None = None


class IncidentWebhook(BaseModel):
    meta: Meta | None = None
    page: PageInfo
    incident: Incident


class ComponentWebhook(BaseModel):
    meta: Meta | None = None
    page: PageInfo
    component_update: ComponentUpdate
    component: Component


class MaintenanceWebhook(BaseModel):
    meta: Meta | None = None
    page: PageInfo
    scheduled_maintenance: ScheduledMaintenance
