from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, select

from app.db import get_session
from app.models import User
from app.schemas import AuthTokenResponse, LoginRequest, SignupRequest, UserPublic
from app.services.auth_security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["Auth API"])
bearer_scheme = HTTPBearer(auto_error=False)


def _user_public(user: User) -> UserPublic:
    return UserPublic(id=str(user.id), name=user.nickname, email=user.email)


def _token_response(user: User) -> AuthTokenResponse:
    return AuthTokenResponse(
        access_token=create_access_token(user.id),
        user=_user_public(user),
    )


@router.post("/signup", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, session: Session = Depends(get_session)) -> AuthTokenResponse:
    existing = session.exec(select(User).where(User.email == payload.email)).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 가입된 이메일입니다.")

    user = User(
        nickname=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return _token_response(user)


@router.post("/login", response_model=AuthTokenResponse)
def login(payload: LoginRequest, session: Session = Depends(get_session)) -> AuthTokenResponse:
    user = session.exec(select(User).where(User.email == payload.email)).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다.",
        )
    return _token_response(user)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: Session = Depends(get_session),
) -> User:
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="인증이 필요합니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise invalid
    subject = decode_access_token(credentials.credentials)
    if subject is None:
        raise invalid
    try:
        user_id = UUID(subject)
    except ValueError:
        raise invalid
    user = session.get(User, user_id)
    if user is None:
        raise invalid
    return user


@router.get("/me", response_model=UserPublic)
def read_current_user(current_user: User = Depends(get_current_user)) -> UserPublic:
    return _user_public(current_user)
