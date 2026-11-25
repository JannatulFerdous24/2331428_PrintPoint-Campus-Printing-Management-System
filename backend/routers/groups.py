"""
/api/groups - student/class/club teams that share print requests.

Group powers come ONLY from ownership and membership (rbac.load_group):
  view                 any member (admins may view for oversight)
  rename / delete      OWNER ONLY
  add/remove members,
  change member flags  OWNER ONLY
Admin moderation (delete any group) lives in /api/admin, not here.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlmodel import Session, select

from audit import log_event
from auth.dependencies import get_current_user
from database import get_session
from models import Group, GroupMember, PrintRequest, User
from rbac import GroupPerm, Permission, get_membership, group_flags, has_permission, load_group

router = APIRouter(prefix="/api/groups", tags=["groups"], dependencies=[Depends(get_current_user)])


# ------------------------------------------------------------------- schemas

class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Group name is required")
        return v


class GroupUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)


class MemberFlags(BaseModel):
    can_create: bool = False
    can_edit: bool = False
    can_assign: bool = False


class MemberAdd(MemberFlags):
    email: EmailStr


class MemberRead(BaseModel):
    user_id: int
    full_name: str
    email: str
    is_owner: bool
    can_create: bool
    can_edit: bool
    can_assign: bool
    joined_at: datetime


class GroupRead(BaseModel):
    id: int
    name: str
    description: Optional[str]
    owner_id: int
    owner_name: str
    member_count: int
    created_at: datetime
    my_permissions: dict[str, bool]


class GroupDetail(GroupRead):
    members: list[MemberRead]


# ------------------------------------------------------------------- helpers

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _members(session: Session, group: Group) -> list[GroupMember]:
    return list(session.exec(select(GroupMember).where(GroupMember.group_id == group.id)
                             .order_by(GroupMember.joined_at)).all())


def _read(session: Session, user: User, group: Group, detail: bool = False):
    members = _members(session, group)
    owner = session.get(User, group.owner_id)
    flags = group_flags(group, next((m for m in members if m.user_id == user.id), None), user)
    base = dict(id=group.id, name=group.name, description=group.description, owner_id=group.owner_id,
                owner_name=owner.full_name if owner else "?", member_count=len(members),
                created_at=group.created_at, my_permissions=flags)
    if not detail:
        return GroupRead(**base)
    rows = []
    for m in members:
        u = session.get(User, m.user_id)
        rows.append(MemberRead(user_id=m.user_id, full_name=u.full_name, email=u.email,
                               is_owner=m.user_id == group.owner_id, can_create=m.can_create,
                               can_edit=m.can_edit, can_assign=m.can_assign, joined_at=m.joined_at))
    return GroupDetail(**base, members=rows)


# ----------------------------------------------------------------- endpoints

@router.post("", response_model=GroupDetail, status_code=201)
def create_group(data: GroupCreate, request: Request, session: Session = Depends(get_session),
                 user: User = Depends(get_current_user)):
    group = Group(name=data.name, description=data.description, owner_id=user.id)
    session.add(group)
    session.flush()
    # The owner is also stored as a member with every flag (keeps queries simple).
    session.add(GroupMember(group_id=group.id, user_id=user.id, can_create=True, can_edit=True,
                            can_assign=True, added_by_id=user.id))
    log_event(session, "group.create", request=request, actor_id=user.id,
              target_type="group", target_id=group.id, details={"name": group.name})
    session.commit()
    session.refresh(group)
    return _read(session, user, group, detail=True)


@router.get("", response_model=list[GroupRead])
def list_groups(all: bool = False, session: Session = Depends(get_session),
                user: User = Depends(get_current_user)):
    if all and has_permission(user, Permission.REQUEST_READ_ALL):
        groups = session.exec(select(Group).order_by(Group.created_at.desc())).all()
    else:
        ids = set(session.exec(select(GroupMember.group_id).where(GroupMember.user_id == user.id)).all())
        ids |= set(session.exec(select(Group.id).where(Group.owner_id == user.id)).all())
        groups = session.exec(select(Group).where(Group.id.in_(ids)).order_by(Group.name)).all() if ids else []
    return [_read(session, user, g) for g in groups]


@router.get("/{group_id}", response_model=GroupDetail)
def get_group(group_id: int, session: Session = Depends(get_session),
              user: User = Depends(get_current_user)):
    group, _ = load_group(session, user, group_id, GroupPerm.VIEW)
    return _read(session, user, group, detail=True)


@router.patch("/{group_id}", response_model=GroupDetail)
def rename_group(group_id: int, data: GroupUpdate, request: Request,
                 session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    group, _ = load_group(session, user, group_id, GroupPerm.MANAGE)  # owner only
    changes = data.model_dump(exclude_unset=True)
    if "name" in changes:
        name = (changes["name"] or "").strip()
        if not name:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Group name is required")
        changes["name"] = name
    old_name = group.name
    for k, v in changes.items():
        setattr(group, k, v)
    group.updated_at = _now()
    session.add(group)
    log_event(session, "group.update", request=request, actor_id=user.id, target_type="group",
              target_id=group.id, details={"old_name": old_name, "new_name": group.name})
    session.commit()
    session.refresh(group)
    return _read(session, user, group, detail=True)


def delete_group_and_detach(session: Session, group: Group) -> int:
    """Delete a group. Its print requests are KEPT and become personal requests."""
    requests = session.exec(select(PrintRequest).where(PrintRequest.group_id == group.id)).all()
    for pr in requests:
        pr.group_id = None
        pr.assignee_id = None
        session.add(pr)
    for m in _members(session, group):
        session.delete(m)
    session.flush()
    session.delete(group)
    return len(requests)


@router.delete("/{group_id}", status_code=204)
def delete_group(group_id: int, request: Request, session: Session = Depends(get_session),
                 user: User = Depends(get_current_user)):
    group, _ = load_group(session, user, group_id, GroupPerm.MANAGE)  # owner only
    name = group.name
    kept = delete_group_and_detach(session, group)
    log_event(session, "group.delete", request=request, actor_id=user.id, target_type="group",
              target_id=group_id, details={"name": name, "requests_kept": kept})
    session.commit()


@router.post("/{group_id}/members", response_model=GroupDetail, status_code=201)
def add_member(group_id: int, data: MemberAdd, request: Request,
               session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    group, _ = load_group(session, user, group_id, GroupPerm.MANAGE)  # owner only
    target = session.exec(select(User).where(User.email == data.email.strip().lower())).first()
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No user with that email")
    if get_membership(session, group.id, target.id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="That user is already a member")
    session.add(GroupMember(group_id=group.id, user_id=target.id, can_create=data.can_create,
                            can_edit=data.can_edit, can_assign=data.can_assign, added_by_id=user.id))
    log_event(session, "group.member_add", request=request, actor_id=user.id, target_type="group",
              target_id=group.id, details={"user_id": target.id, **data.model_dump(exclude={"email"})})
    session.commit()
    return _read(session, user, group, detail=True)


@router.patch("/{group_id}/members/{user_id}", response_model=GroupDetail)
def update_member(group_id: int, user_id: int, data: MemberFlags, request: Request,
                  session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    group, _ = load_group(session, user, group_id, GroupPerm.MANAGE)  # owner only
    if user_id == group.owner_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="The owner's permissions cannot be changed")
    m = get_membership(session, group.id, user_id)
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Member not found")
    m.can_create, m.can_edit, m.can_assign = data.can_create, data.can_edit, data.can_assign
    session.add(m)
    log_event(session, "group.member_update", request=request, actor_id=user.id, target_type="group",
              target_id=group.id, details={"user_id": user_id, **data.model_dump()})
    session.commit()
    return _read(session, user, group, detail=True)


@router.delete("/{group_id}/members/{user_id}", response_model=GroupDetail)
def remove_member(group_id: int, user_id: int, request: Request,
                  session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    group, _ = load_group(session, user, group_id, GroupPerm.MANAGE)  # owner only
    if user_id == group.owner_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="The owner cannot be removed from the group")
    m = get_membership(session, group.id, user_id)
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Member not found")
    for pr in session.exec(select(PrintRequest).where(PrintRequest.group_id == group.id,
                                                      PrintRequest.assignee_id == user_id)).all():
        pr.assignee_id = None
        session.add(pr)
    session.delete(m)
    log_event(session, "group.member_remove", request=request, actor_id=user.id, target_type="group",
              target_id=group.id, details={"user_id": user_id})
    session.commit()
    return _read(session, user, group, detail=True)
