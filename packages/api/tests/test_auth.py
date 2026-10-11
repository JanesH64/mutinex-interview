from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest

from mc_api.auth import JWT_SECRET, create_token
from mc_api.models import Organization
from mc_shared import UserRole


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_login_issues_token_with_only_the_user_id(client, make_user):
    user = make_user(UserRole.CREW)
    response = client.post("/auth/login", json={"username": user.username})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    claims = jwt.decode(body["access_token"], JWT_SECRET, algorithms=["HS256"])
    assert claims["sub"] == str(user.id)
    assert set(claims) == {"sub", "exp"}
    expected = datetime.now(UTC) + timedelta(hours=12)
    assert abs(datetime.fromtimestamp(claims["exp"], UTC) - expected) < timedelta(seconds=60)


def test_login_unknown_user_gives_401(client):
    response = client.post("/auth/login", json={"username": f"nobody-{uuid4()}"})
    assert response.status_code == 401


def test_me_returns_user_and_org(client, make_user, session):
    lead = make_user(UserRole.LEAD)
    make_user(UserRole.CREW)  # another org
    response = client.get("/me", headers=bearer(create_token(lead.id)))
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(lead.id)
    assert body["username"] == lead.username
    assert body["display_name"] == lead.display_name
    assert body["role"] == "LEAD"
    assert body["org_id"] == str(lead.org_id)
    assert body["org_name"] == session.get(Organization, lead.org_id).name


def test_me_loads_the_role_on_each_request(client, make_user, session):
    user = make_user(UserRole.LEAD)
    token = create_token(user.id)
    assert client.get("/me", headers=bearer(token)).json()["role"] == "LEAD"
    user.role = UserRole.DIRECTOR
    session.flush()
    response = client.get("/me", headers=bearer(token))
    assert response.json()["role"] == "DIRECTOR"


def test_me_without_header_gives_401(client):
    response = client.get("/me")
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_me_with_wrong_secret_gives_401(client, make_user):
    user = make_user(UserRole.CREW)
    claims = {"sub": str(user.id), "exp": datetime.now(UTC) + timedelta(hours=1)}
    token = jwt.encode(claims, "x" * 32, algorithm="HS256")
    response = client.get("/me", headers=bearer(token))
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_me_with_expired_token_gives_401(client, make_user):
    user = make_user(UserRole.CREW)
    token = create_token(user.id, now=datetime.now(UTC) - timedelta(hours=13))
    assert client.get("/me", headers=bearer(token)).status_code == 401


def test_me_for_deleted_user_gives_401(client, make_user, session):
    user = make_user(UserRole.CREW)
    token = create_token(user.id)
    session.delete(user)
    session.flush()
    assert client.get("/me", headers=bearer(token)).status_code == 401


@pytest.mark.parametrize("kind", ["garbage", "alg-none", "bad-sub"])
def test_me_with_invalid_token_gives_401(client, make_user, kind):
    user = make_user(UserRole.CREW)
    exp = datetime.now(UTC) + timedelta(hours=1)
    token = {
        "garbage": "garbage",
        "alg-none": jwt.encode({"sub": str(user.id), "exp": exp}, None, algorithm="none"),
        "bad-sub": jwt.encode({"sub": "not-a-uuid", "exp": exp}, JWT_SECRET, algorithm="HS256"),
    }[kind]
    response = client.get("/me", headers=bearer(token))
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_user_role_lives_in_mc_shared():
    import mc_shared
    from mc_api import models

    assert models.UserRole is mc_shared.UserRole
