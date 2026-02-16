"""
Certify Intel - Team Features Router (v5.2.0)
Handles team management, annotations, and role-based dashboard configuration.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import json

from database import (
    get_db, User, Team, TeamMembership, CompetitorAnnotation,
    AnnotationReply, DashboardConfiguration, TeamActivity, Competitor
)
from extended_features import auth_manager

router = APIRouter(prefix="/api/teams", tags=["Teams"])

# OAuth2 scheme for authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)


async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """Verify JWT token and return current user."""
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = auth_manager.verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = db.query(User).filter(User.email == payload.get("sub")).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user


# =============================================================================
# Pydantic Models
# =============================================================================

class TeamCreate(BaseModel):
    name: str
    description: Optional[str] = None

class TeamResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    member_count: int = 0
    created_at: datetime

class TeamMemberAdd(BaseModel):
    user_email: str
    role: str = "member"  # owner, admin, member

class TeamMemberResponse(BaseModel):
    user_id: int
    email: str
    full_name: Optional[str]
    role: str
    joined_at: datetime

class AnnotationCreate(BaseModel):
    competitor_id: int
    title: Optional[str] = None
    content: str
    annotation_type: str = "note"  # note, insight, warning, opportunity, action_item
    priority: str = "normal"  # low, normal, high, critical
    team_id: Optional[int] = None  # NULL = personal note
    is_public: bool = True
    field_name: Optional[str] = None
    dimension_id: Optional[str] = None

class AnnotationResponse(BaseModel):
    id: int
    competitor_id: int
    competitor_name: Optional[str] = None
    user_email: str
    user_name: Optional[str] = None
    title: Optional[str]
    content: str
    annotation_type: str
    priority: str
    is_public: bool
    is_pinned: bool
    replies_count: int = 0
    created_at: datetime
    updated_at: datetime

class ReplyCreate(BaseModel):
    content: str

class DashboardConfigUpdate(BaseModel):
    layout: Optional[str] = None
    widgets: Optional[dict] = None
    default_threat_filter: Optional[str] = None
    default_sort: Optional[str] = None
    items_per_page: Optional[int] = None
    pinned_competitors: Optional[List[int]] = None


# =============================================================================
# Team Management Endpoints (5.2.0-001)
# =============================================================================

@router.post("", response_model=TeamResponse)
async def create_team(
    team_data: TeamCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new team. User becomes the owner."""
    existing = db.query(Team).filter(Team.name == team_data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Team name already exists")

    team = Team(
        name=team_data.name,
        description=team_data.description,
        created_by=current_user.id
    )
    db.add(team)
    db.commit()
    db.refresh(team)

    # Add creator as owner
    membership = TeamMembership(
        team_id=team.id,
        user_id=current_user.id,
        role="owner"
    )
    db.add(membership)
    db.commit()

    return TeamResponse(
        id=team.id,
        name=team.name,
        description=team.description,
        member_count=1,
        created_at=team.created_at
    )


@router.get("", response_model=List[TeamResponse])
async def list_teams(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all teams the current user belongs to."""
    memberships = db.query(TeamMembership).filter(
        TeamMembership.user_id == current_user.id
    ).all()

    team_ids = [m.team_id for m in memberships]
    teams = db.query(Team).filter(Team.id.in_(team_ids), Team.is_active == True).all()

    result = []
    for team in teams:
        member_count = db.query(TeamMembership).filter(
            TeamMembership.team_id == team.id
        ).count()
        result.append(TeamResponse(
            id=team.id,
            name=team.name,
            description=team.description,
            member_count=member_count,
            created_at=team.created_at
        ))

    return result


@router.get("/{team_id}", response_model=TeamResponse)
async def get_team(
    team_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get team details."""
    team = db.query(Team).filter(Team.id == team_id, Team.is_active == True).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # Check membership
    membership = db.query(TeamMembership).filter(
        TeamMembership.team_id == team_id,
        TeamMembership.user_id == current_user.id
    ).first()

    if not membership and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not a member of this team")

    member_count = db.query(TeamMembership).filter(
        TeamMembership.team_id == team_id
    ).count()

    return TeamResponse(
        id=team.id,
        name=team.name,
        description=team.description,
        member_count=member_count,
        created_at=team.created_at
    )


@router.get("/{team_id}/members", response_model=List[TeamMemberResponse])
async def get_team_members(
    team_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all members of a team."""
    memberships = db.query(TeamMembership).filter(
        TeamMembership.team_id == team_id
    ).all()

    result = []
    for m in memberships:
        user = db.query(User).filter(User.id == m.user_id).first()
        if user:
            result.append(TeamMemberResponse(
                user_id=user.id,
                email=user.email,
                full_name=user.full_name,
                role=m.role,
                joined_at=m.joined_at
            ))

    return result


@router.post("/{team_id}/members")
async def add_team_member(
    team_id: int,
    member_data: TeamMemberAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a user to a team."""
    # Check if current user has permission
    membership = db.query(TeamMembership).filter(
        TeamMembership.team_id == team_id,
        TeamMembership.user_id == current_user.id,
        TeamMembership.role.in_(["owner", "admin"])
    ).first()

    if not membership and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to add members")

    # Find user to add
    user = db.query(User).filter(User.email == member_data.user_email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if already a member
    existing = db.query(TeamMembership).filter(
        TeamMembership.team_id == team_id,
        TeamMembership.user_id == user.id
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="User is already a team member")

    new_membership = TeamMembership(
        team_id=team_id,
        user_id=user.id,
        role=member_data.role,
        invited_by=current_user.id
    )
    db.add(new_membership)
    db.commit()

    return {"message": f"Added {user.email} to team", "user_id": user.id}


@router.delete("/{team_id}/members/{user_id}")
async def remove_team_member(
    team_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Remove a user from a team."""
    # Check if current user has permission
    membership = db.query(TeamMembership).filter(
        TeamMembership.team_id == team_id,
        TeamMembership.user_id == current_user.id,
        TeamMembership.role.in_(["owner", "admin"])
    ).first()

    if not membership and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to remove members")

    target = db.query(TeamMembership).filter(
        TeamMembership.team_id == team_id,
        TeamMembership.user_id == user_id
    ).first()

    if not target:
        raise HTTPException(status_code=404, detail="Member not found")

    if target.role == "owner":
        raise HTTPException(status_code=400, detail="Cannot remove team owner")

    db.delete(target)
    db.commit()

    return {"message": "Member removed"}


# =============================================================================
# Shared Annotations Endpoints (5.2.0-003)
# =============================================================================

@router.post("/annotations", response_model=AnnotationResponse)
async def create_annotation(
    data: AnnotationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new annotation on a competitor."""
    competitor = db.query(Competitor).filter(Competitor.id == data.competitor_id).first()
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")

    annotation = CompetitorAnnotation(
        competitor_id=data.competitor_id,
        user_id=current_user.id,
        team_id=data.team_id,
        title=data.title,
        content=data.content,
        annotation_type=data.annotation_type,
        priority=data.priority,
        is_public=data.is_public,
        field_name=data.field_name,
        dimension_id=data.dimension_id
    )
    db.add(annotation)
    db.commit()
    db.refresh(annotation)

    # Log team activity
    if data.team_id:
        activity = TeamActivity(
            team_id=data.team_id,
            user_id=current_user.id,
            user_email=current_user.email,
            activity_type="annotation",
            competitor_id=data.competitor_id,
            activity_details=json.dumps({
                "annotation_id": annotation.id,
                "type": data.annotation_type,
                "title": data.title
            })
        )
        db.add(activity)
        db.commit()

    return AnnotationResponse(
        id=annotation.id,
        competitor_id=annotation.competitor_id,
        competitor_name=competitor.name,
        user_email=current_user.email,
        user_name=current_user.full_name,
        title=annotation.title,
        content=annotation.content,
        annotation_type=annotation.annotation_type,
        priority=annotation.priority,
        is_public=annotation.is_public,
        is_pinned=annotation.is_pinned,
        replies_count=0,
        created_at=annotation.created_at,
        updated_at=annotation.updated_at
    )


@router.get("/annotations/competitor/{competitor_id}", response_model=List[AnnotationResponse])
async def get_competitor_annotations(
    competitor_id: int,
    annotation_type: Optional[str] = None,
    include_private: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all annotations for a competitor."""
    query = db.query(CompetitorAnnotation).filter(
        CompetitorAnnotation.competitor_id == competitor_id
    )

    if annotation_type:
        query = query.filter(CompetitorAnnotation.annotation_type == annotation_type)

    if not include_private:
        # Show public annotations or user's own
        query = query.filter(
            (CompetitorAnnotation.is_public == True) |
            (CompetitorAnnotation.user_id == current_user.id)
        )

    annotations = query.order_by(
        CompetitorAnnotation.is_pinned.desc(),
        CompetitorAnnotation.created_at.desc()
    ).all()

    result = []
    for a in annotations:
        user = db.query(User).filter(User.id == a.user_id).first()
        competitor = db.query(Competitor).filter(Competitor.id == a.competitor_id).first()
        replies_count = db.query(AnnotationReply).filter(
            AnnotationReply.annotation_id == a.id
        ).count()

        result.append(AnnotationResponse(
            id=a.id,
            competitor_id=a.competitor_id,
            competitor_name=competitor.name if competitor else None,
            user_email=user.email if user else "Unknown",
            user_name=user.full_name if user else None,
            title=a.title,
            content=a.content,
            annotation_type=a.annotation_type,
            priority=a.priority,
            is_public=a.is_public,
            is_pinned=a.is_pinned,
            replies_count=replies_count,
            created_at=a.created_at,
            updated_at=a.updated_at
        ))

    return result


@router.get("/annotations/team/{team_id}", response_model=List[AnnotationResponse])
async def get_team_annotations(
    team_id: int,
    limit: int = Query(default=50, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get recent annotations from a team."""
    annotations = db.query(CompetitorAnnotation).filter(
        CompetitorAnnotation.team_id == team_id,
        CompetitorAnnotation.is_public == True
    ).order_by(
        CompetitorAnnotation.created_at.desc()
    ).limit(limit).all()

    result = []
    for a in annotations:
        user = db.query(User).filter(User.id == a.user_id).first()
        competitor = db.query(Competitor).filter(Competitor.id == a.competitor_id).first()
        replies_count = db.query(AnnotationReply).filter(
            AnnotationReply.annotation_id == a.id
        ).count()

        result.append(AnnotationResponse(
            id=a.id,
            competitor_id=a.competitor_id,
            competitor_name=competitor.name if competitor else None,
            user_email=user.email if user else "Unknown",
            user_name=user.full_name if user else None,
            title=a.title,
            content=a.content,
            annotation_type=a.annotation_type,
            priority=a.priority,
            is_public=a.is_public,
            is_pinned=a.is_pinned,
            replies_count=replies_count,
            created_at=a.created_at,
            updated_at=a.updated_at
        ))

    return result


@router.put("/annotations/{annotation_id}")
async def update_annotation(
    annotation_id: int,
    data: AnnotationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update an annotation (owner only)."""
    annotation = db.query(CompetitorAnnotation).filter(
        CompetitorAnnotation.id == annotation_id
    ).first()

    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")

    if annotation.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to edit this annotation")

    annotation.title = data.title
    annotation.content = data.content
    annotation.annotation_type = data.annotation_type
    annotation.priority = data.priority
    annotation.is_public = data.is_public
    annotation.updated_at = datetime.utcnow()

    db.commit()

    return {"message": "Annotation updated", "id": annotation_id}


@router.delete("/annotations/{annotation_id}")
async def delete_annotation(
    annotation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete an annotation (owner only)."""
    annotation = db.query(CompetitorAnnotation).filter(
        CompetitorAnnotation.id == annotation_id
    ).first()

    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")

    if annotation.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to delete this annotation")

    # Delete replies first
    db.query(AnnotationReply).filter(AnnotationReply.annotation_id == annotation_id).delete()
    db.delete(annotation)
    db.commit()

    return {"message": "Annotation deleted"}


@router.post("/annotations/{annotation_id}/pin")
async def toggle_annotation_pin(
    annotation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Toggle pin status of an annotation."""
    annotation = db.query(CompetitorAnnotation).filter(
        CompetitorAnnotation.id == annotation_id
    ).first()

    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")

    annotation.is_pinned = not annotation.is_pinned
    db.commit()

    return {"message": "Pin toggled", "is_pinned": annotation.is_pinned}


@router.post("/annotations/{annotation_id}/replies")
async def add_reply(
    annotation_id: int,
    data: ReplyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a reply to an annotation."""
    annotation = db.query(CompetitorAnnotation).filter(
        CompetitorAnnotation.id == annotation_id
    ).first()

    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")

    reply = AnnotationReply(
        annotation_id=annotation_id,
        user_id=current_user.id,
        content=data.content
    )
    db.add(reply)
    db.commit()
    db.refresh(reply)

    return {
        "id": reply.id,
        "annotation_id": annotation_id,
        "user_email": current_user.email,
        "content": reply.content,
        "created_at": reply.created_at.isoformat()
    }


@router.get("/annotations/{annotation_id}/replies")
async def get_replies(
    annotation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all replies to an annotation."""
    replies = db.query(AnnotationReply).filter(
        AnnotationReply.annotation_id == annotation_id
    ).order_by(AnnotationReply.created_at.asc()).all()

    result = []
    for r in replies:
        user = db.query(User).filter(User.id == r.user_id).first()
        result.append({
            "id": r.id,
            "user_email": user.email if user else "Unknown",
            "user_name": user.full_name if user else None,
            "content": r.content,
            "created_at": r.created_at.isoformat()
        })

    return result


# =============================================================================
# Role-Based Dashboard Configuration (5.2.0-002)
# =============================================================================

# Default configurations per role
DEFAULT_ROLE_CONFIGS = {
    "admin": {
        "layout": "detailed",
        "can_view_analytics": True,
        "can_view_financials": True,
        "can_edit_competitors": True,
        "can_manage_users": True,
        "can_export_data": True,
        "can_trigger_refresh": True
    },
    "analyst": {
        "layout": "standard",
        "can_view_analytics": True,
        "can_view_financials": True,
        "can_edit_competitors": True,
        "can_manage_users": False,
        "can_export_data": True,
        "can_trigger_refresh": True
    },
    "viewer": {
        "layout": "compact",
        "can_view_analytics": True,
        "can_view_financials": False,
        "can_edit_competitors": False,
        "can_manage_users": False,
        "can_export_data": True,
        "can_trigger_refresh": False
    }
}


@router.get("/dashboard/config")
async def get_dashboard_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the current user's dashboard configuration."""
    # First check for user-specific config
    user_config = db.query(DashboardConfiguration).filter(
        DashboardConfiguration.config_type == "user",
        DashboardConfiguration.config_key == str(current_user.id)
    ).first()

    if user_config:
        return {
            "config_source": "user",
            "layout": user_config.layout,
            "widgets": json.loads(user_config.widgets) if user_config.widgets else None,
            "default_threat_filter": user_config.default_threat_filter,
            "default_sort": user_config.default_sort,
            "items_per_page": user_config.items_per_page,
            "permissions": {
                "can_view_analytics": user_config.can_view_analytics,
                "can_view_financials": user_config.can_view_financials,
                "can_edit_competitors": user_config.can_edit_competitors,
                "can_manage_users": user_config.can_manage_users,
                "can_export_data": user_config.can_export_data,
                "can_trigger_refresh": user_config.can_trigger_refresh
            },
            "pinned_competitors": json.loads(user_config.pinned_competitors) if user_config.pinned_competitors else [],
            "favorite_reports": json.loads(user_config.favorite_reports) if user_config.favorite_reports else []
        }

    # Fall back to role-based config
    role_config = db.query(DashboardConfiguration).filter(
        DashboardConfiguration.config_type == "role",
        DashboardConfiguration.config_key == current_user.role
    ).first()

    if role_config:
        return {
            "config_source": "role",
            "layout": role_config.layout,
            "widgets": json.loads(role_config.widgets) if role_config.widgets else None,
            "default_threat_filter": role_config.default_threat_filter,
            "default_sort": role_config.default_sort,
            "items_per_page": role_config.items_per_page,
            "permissions": {
                "can_view_analytics": role_config.can_view_analytics,
                "can_view_financials": role_config.can_view_financials,
                "can_edit_competitors": role_config.can_edit_competitors,
                "can_manage_users": role_config.can_manage_users,
                "can_export_data": role_config.can_export_data,
                "can_trigger_refresh": role_config.can_trigger_refresh
            },
            "pinned_competitors": [],
            "favorite_reports": []
        }

    # Fall back to default role config
    defaults = DEFAULT_ROLE_CONFIGS.get(current_user.role, DEFAULT_ROLE_CONFIGS["viewer"])
    return {
        "config_source": "default",
        "layout": defaults["layout"],
        "widgets": None,
        "default_threat_filter": "all",
        "default_sort": "threat_level",
        "items_per_page": 10,
        "permissions": {
            "can_view_analytics": defaults["can_view_analytics"],
            "can_view_financials": defaults["can_view_financials"],
            "can_edit_competitors": defaults["can_edit_competitors"],
            "can_manage_users": defaults["can_manage_users"],
            "can_export_data": defaults["can_export_data"],
            "can_trigger_refresh": defaults["can_trigger_refresh"]
        },
        "pinned_competitors": [],
        "favorite_reports": []
    }


@router.put("/dashboard/config")
async def update_dashboard_config(
    data: DashboardConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update the current user's dashboard configuration."""
    config = db.query(DashboardConfiguration).filter(
        DashboardConfiguration.config_type == "user",
        DashboardConfiguration.config_key == str(current_user.id)
    ).first()

    if not config:
        # Create new user config
        config = DashboardConfiguration(
            config_type="user",
            config_key=str(current_user.id)
        )
        db.add(config)

    # Update fields
    if data.layout:
        config.layout = data.layout
    if data.widgets is not None:
        config.widgets = json.dumps(data.widgets)
    if data.default_threat_filter:
        config.default_threat_filter = data.default_threat_filter
    if data.default_sort:
        config.default_sort = data.default_sort
    if data.items_per_page:
        config.items_per_page = data.items_per_page
    if data.pinned_competitors is not None:
        config.pinned_competitors = json.dumps(data.pinned_competitors)

    config.updated_at = datetime.utcnow()
    db.commit()

    return {"message": "Dashboard configuration updated"}


@router.post("/dashboard/config/role/{role}")
async def set_role_dashboard_config(
    role: str,
    data: DashboardConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Set dashboard configuration for a role (admin only)."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    if role not in ["admin", "analyst", "viewer"]:
        raise HTTPException(status_code=400, detail="Invalid role")

    config = db.query(DashboardConfiguration).filter(
        DashboardConfiguration.config_type == "role",
        DashboardConfiguration.config_key == role
    ).first()

    if not config:
        config = DashboardConfiguration(
            config_type="role",
            config_key=role
        )
        db.add(config)

    if data.layout:
        config.layout = data.layout
    if data.widgets is not None:
        config.widgets = json.dumps(data.widgets)
    if data.default_threat_filter:
        config.default_threat_filter = data.default_threat_filter
    if data.default_sort:
        config.default_sort = data.default_sort
    if data.items_per_page:
        config.items_per_page = data.items_per_page

    config.updated_at = datetime.utcnow()
    db.commit()

    return {"message": f"Role '{role}' dashboard configuration updated"}


@router.post("/dashboard/pin/{competitor_id}")
async def pin_competitor(
    competitor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Pin a competitor to the user's dashboard."""
    config = db.query(DashboardConfiguration).filter(
        DashboardConfiguration.config_type == "user",
        DashboardConfiguration.config_key == str(current_user.id)
    ).first()

    if not config:
        config = DashboardConfiguration(
            config_type="user",
            config_key=str(current_user.id),
            pinned_competitors="[]"
        )
        db.add(config)

    pinned = json.loads(config.pinned_competitors or "[]")

    if competitor_id not in pinned:
        pinned.append(competitor_id)
        config.pinned_competitors = json.dumps(pinned)
        db.commit()

    return {"message": "Competitor pinned", "pinned": pinned}


@router.delete("/dashboard/pin/{competitor_id}")
async def unpin_competitor(
    competitor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Unpin a competitor from the user's dashboard."""
    config = db.query(DashboardConfiguration).filter(
        DashboardConfiguration.config_type == "user",
        DashboardConfiguration.config_key == str(current_user.id)
    ).first()

    if config:
        pinned = json.loads(config.pinned_competitors or "[]")
        if competitor_id in pinned:
            pinned.remove(competitor_id)
            config.pinned_competitors = json.dumps(pinned)
            db.commit()

    return {"message": "Competitor unpinned"}


# =============================================================================
# Team Activity Feed
# =============================================================================

@router.get("/{team_id}/activity")
async def get_team_activity(
    team_id: int,
    limit: int = Query(default=20, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get recent activity for a team."""
    activities = db.query(TeamActivity).filter(
        TeamActivity.team_id == team_id
    ).order_by(
        TeamActivity.created_at.desc()
    ).limit(limit).all()

    result = []
    for a in activities:
        competitor = None
        if a.competitor_id:
            competitor = db.query(Competitor).filter(Competitor.id == a.competitor_id).first()

        result.append({
            "id": a.id,
            "user_email": a.user_email,
            "activity_type": a.activity_type,
            "activity_details": json.loads(a.activity_details) if a.activity_details else None,
            "competitor_id": a.competitor_id,
            "competitor_name": competitor.name if competitor else None,
            "created_at": a.created_at.isoformat()
        })

    return result
