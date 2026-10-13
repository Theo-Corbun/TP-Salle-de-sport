from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import time
from typing import Annotated, Any
from fastapi import Depends, FastAPI, HTTPException, Header, Query, Request, Response, Security, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from sqlmodel import Field as SQLField, Session, SQLModel, create_engine, func, select

app = FastAPI(title="API Salle de Sport")

sqlite_file_name = "Salle-de-sport.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"
connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]

API_KEY_SECRET = "gym_secret_key_2026"
api_key_header_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)


# ==========================================
# 1. Gestion centralisée des erreurs (RFC 9457)
# ==========================================


def build_problem_detail(
    request: Request,
    status_code: int,
    title: str,
    detail: str,
    invalid_params: list[dict[str, Any]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    content: dict[str, Any] = {
        "type": "about:blank",
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": request.url.path,
    }
    if invalid_params:
        content["invalid-params"] = invalid_params

    resp_headers = {"Content-Type": "application/problem+json"}
    if headers:
        resp_headers.update(headers)

    return JSONResponse(
        status_code=status_code,
        content=content,
        headers=resp_headers,
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    titles = {
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        406: "Not Acceptable",
        409: "Conflict",
        422: "Unprocessable Entity",
        429: "Too Many Requests",
        500: "Internal Server Error",
    }
    title = titles.get(exc.status_code, "Error")
    return build_problem_detail(
        request=request,
        status_code=exc.status_code,
        title=title,
        detail=str(exc.detail),
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    invalid_params = []
    for err in exc.errors():
        loc = " -> ".join([str(x) for x in err.get("loc", []) if x != "body"])
        invalid_params.append({
            "name": loc or "corps",
            "reason": err.get("msg", "Valeur invalide"),
        })

    return build_problem_detail(
        request=request,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        title="Unprocessable Entity",
        detail="Les données soumises ne respectent pas les critères de validation.",
        invalid_params=invalid_params,
    )


# ==========================================
# 2. Sécurité : Vérification Clé API
# ==========================================


def verify_api_key(
    api_key: Annotated[str | None, Security(api_key_header_scheme)]
):
    if not api_key or api_key != API_KEY_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé API manquante ou invalide dans l'en-tête 'X-API-Key'.",
        )
    return api_key


AuthDep = Annotated[str, Depends(verify_api_key)]


# ==========================================
# 3. Middlewares : Rate Limiting & Négociation
# ==========================================

RATE_LIMIT_MAX = 60
RATE_LIMIT_WINDOW = 60.0
request_history: dict[str, list[float]] = defaultdict(list)


@app.middleware("http")
async def rate_limiting_middleware(request: Request, call_next):
    if not request.url.path.startswith(("/docs", "/openapi.json")):
        client_ip = request.client.host if request.client else "127.0.0.1"
        now = time.time()
        window_start = now - RATE_LIMIT_WINDOW

        timestamps = [t for t in request_history[client_ip] if t > window_start]
        request_history[client_ip] = timestamps

        if len(timestamps) >= RATE_LIMIT_MAX:
            return build_problem_detail(
                request=request,
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                title="Too Many Requests",
                detail="Limite de requêtes atteinte. Veuillez patienter avant de réessayer.",
                headers={"Retry-After": "60"},
            )

        request_history[client_ip].append(now)

    return await call_next(request)


@app.middleware("http")
async def content_negotiation_middleware(request: Request, call_next):
    if not request.url.path.startswith(("/docs", "/openapi.json")):
        accept_header = request.headers.get("accept", "*/*")
        is_acceptable = any(
            mime in accept_header
            for mime in ["*/*", "application/json", "application/*"]
        )
        if not is_acceptable:
            return build_problem_detail(
                request=request,
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
                title="Not Acceptable",
                detail=f"L'API ne peut produire la réponse au format demandé dans 'Accept: {accept_header}'. Formats acceptés : application/json.",
            )
    return await call_next(request)


# ==========================================
# 4. Modèles de données (Tables et Schémas)
# ==========================================


class Cours(SQLModel, table=True):
    __tablename__ = "cours"
    id: int | None = SQLField(default=None, primary_key=True)
    type: str
    coach_id: int
    capacite: int = SQLField(default=20)
    jour_semaine: int = SQLField(default=1)
    heure_debut: str = SQLField(default="10:00")
    duree_min: int = SQLField(default=60)
    periode_debut: str = SQLField(default="2026-09-01")
    periode_fin: str = SQLField(default="2027-06-30")
    fuseau: str = SQLField(default="Europe/Paris")


class CoursCreate(BaseModel):
    type: str = Field(min_length=2, max_length=50)
    coach_id: int = Field(gt=0)
    capacite: int = Field(default=20, gt=0, le=100)
    jour_semaine: int = Field(default=1, ge=1, le=7, description="Jour de 1 (Lundi) à 7 (Dimanche)")
    heure_debut: str = Field(default="10:00")
    duree_min: int = Field(default=60, ge=15, le=180)
    periode_debut: str = Field(default="2026-09-01")
    periode_fin: str = Field(default="2027-06-30")
    fuseau: str = Field(default="Europe/Paris")


class CoursUpdate(BaseModel):
    type: str | None = Field(default=None, min_length=2, max_length=50)
    coach_id: int | None = Field(default=None, gt=0)
    capacite: int | None = Field(default=None, gt=0, le=100)
    jour_semaine: int | None = Field(default=None, ge=1, le=7)
    heure_debut: str | None = None
    duree_min: int | None = Field(default=None, ge=15, le=180)
    periode_debut: str | None = None
    periode_fin: str | None = None
    fuseau: str | None = None
    

class Adherent(SQLModel, table=True):
    __tablename__ = "adherents"
    id: int | None = SQLField(default=None, primary_key=True)
    nom: str
    email: str


class AdherentCreate(BaseModel):
    nom: str = Field(min_length=2, max_length=100)
    email: str = Field(pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")


class AdherentUpdate(BaseModel):
    nom: str | None = Field(default=None, min_length=2, max_length=100)
    email: str | None = Field(default=None, pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")


class Creneau(SQLModel, table=True):
    __tablename__ = "creneaux"
    id: int | None = SQLField(default=None, primary_key=True)
    cours_id: int
    debut: str
    fin: str
    places_prises: int = SQLField(default=0)


class CreneauCreate(BaseModel):
    debut: str = Field(description="Ex: 2026-10-20 10:00:00")
    fin: str = Field(description="Ex: 2026-10-20 11:00:00")


class Reservation(SQLModel, table=True):
    __tablename__ = "reservations"
    id: int | None = SQLField(default=None, primary_key=True)
    creneau_id: int
    adherent_id: int
    statut: str = SQLField(default="confirmee")
    cree_le: str | None = None


class ReservationCreate(BaseModel):
    adherent_id: int = Field(gt=0)


# ==========================================
# 5. Modèles de Pagination & Utilitaire Cache
# ==========================================


class PaginationMeta(BaseModel):
    offset: int
    limit: int
    total: int


class PaginationLinks(BaseModel):
    next: str | None = None
    prev: str | None = None


class PagedResponse(BaseModel):
    data: list[Any]
    pagination: PaginationMeta
    links: PaginationLinks


def generate_etag(data: dict[str, Any]) -> str:
    serialized = json.dumps(data, sort_keys=True)
    return f'"{hashlib.md5(serialized.encode()).hexdigest()}"'


# ==========================================
# 6. Routes : Cours
# ==========================================


@app.get("/cours", response_model=PagedResponse)
def list_cours(
    session: SessionDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    type: str | None = None,
    tri: str = Query(default="asc", pattern="^(asc|desc)$"),
):
    statement = select(Cours)
    if type:
        statement = statement.where(Cours.type.ilike(f"%{type}%"))

    count_statement = select(func.count()).select_from(statement.subquery())
    total = session.exec(count_statement).one()

    if tri == "desc":
        statement = statement.order_by(Cours.type.desc(), Cours.id.desc())
    else:
        statement = statement.order_by(Cours.type.asc(), Cours.id.asc())

    items = session.exec(statement.offset(offset).limit(limit)).all()

    base_url = f"/cours?limit={limit}&tri={tri}"
    if type:
        base_url += f"&type={type}"

    next_link = (
        f"{base_url}&offset={offset + limit}"
        if (offset + limit) < total
        else None
    )
    prev_link = (
        f"{base_url}&offset={max(0, offset - limit)}" if offset > 0 else None
    )

    return PagedResponse(
        data=items,
        pagination=PaginationMeta(offset=offset, limit=limit, total=total),
        links=PaginationLinks(next=next_link, prev=prev_link),
    )


@app.get("/cours/{cours_id}")
def get_cours(
    cours_id: int,
    session: SessionDep,
    response: Response,
    if_none_match: Annotated[str | None, Header()] = None,
):
    cours = session.get(Cours, cours_id)
    if not cours:
        raise HTTPException(status_code=404, detail=f"Cours avec l'identifiant {cours_id} introuvable.")

    cours_data = cours.model_dump()
    etag = generate_etag(cours_data)

    if if_none_match and if_none_match.strip() == etag:
        return Response(
            status_code=status.HTTP_304_NOT_MODIFIED,
            headers={
                "ETag": etag,
                "Cache-Control": "private, max-age=60",
            },
        )

    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "private, max-age=60"
    return cours_data


@app.post("/cours", status_code=status.HTTP_201_CREATED, response_model=Cours)
def create_cours(
    cours_in: CoursCreate,
    response: Response,
    session: SessionDep,
    _auth: AuthDep,
):
    cours = Cours.model_validate(cours_in)
    session.add(cours)
    session.commit()
    session.refresh(cours)
    response.headers["Location"] = f"/cours/{cours.id}"
    return cours


@app.patch("/cours/{cours_id}", response_model=Cours)
def update_cours(
    cours_id: int,
    cours_in: CoursUpdate,
    session: SessionDep,
    _auth: AuthDep,
):
    cours = session.get(Cours, cours_id)
    if not cours:
        raise HTTPException(status_code=404, detail=f"Cours avec l'identifiant {cours_id} introuvable.")

    data_to_update = cours_in.model_dump(exclude_unset=True)
    for key, value in data_to_update.items():
        setattr(cours, key, value)

    session.add(cours)
    session.commit()
    session.refresh(cours)
    return cours


@app.delete("/cours/{cours_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cours(
    cours_id: int,
    session: SessionDep,
    _auth: AuthDep,
):
    cours = session.get(Cours, cours_id)
    if not cours:
        raise HTTPException(status_code=404, detail=f"Cours avec l'identifiant {cours_id} introuvable.")
    session.delete(cours)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ==========================================
# 7. Sous-ressources (/cours/{cours_id}/creneaux)
# ==========================================


@app.get("/cours/{cours_id}/creneaux", response_model=list[Creneau])
def list_creneaux_for_cours(cours_id: int, session: SessionDep):
    cours = session.get(Cours, cours_id)
    if not cours:
        raise HTTPException(status_code=404, detail=f"Cours avec l'identifiant {cours_id} introuvable.")
    return session.exec(select(Creneau).where(Creneau.cours_id == cours_id)).all()


@app.post(
    "/cours/{cours_id}/creneaux",
    status_code=status.HTTP_201_CREATED,
    response_model=Creneau,
)
def create_creneau_for_cours(
    cours_id: int,
    creneau_in: CreneauCreate,
    response: Response,
    session: SessionDep,
    _auth: AuthDep,
):
    cours = session.get(Cours, cours_id)
    if not cours:
        raise HTTPException(status_code=404, detail=f"Cours avec l'identifiant {cours_id} introuvable.")

    creneau = Creneau(
        cours_id=cours_id,
        debut=creneau_in.debut,
        fin=creneau_in.fin,
        places_prises=0,
    )
    session.add(creneau)
    session.commit()
    session.refresh(creneau)
    response.headers["Location"] = f"/cours/{cours_id}/creneaux/{creneau.id}"
    return creneau


# ==========================================
# 8. Routes : Adhérents
# ==========================================


@app.get("/adherents", response_model=list[Adherent])
def list_adherents(
    session: SessionDep,
    offset: int = 0,
    limit: Annotated[int, Query(le=100)] = 20,
):
    return session.exec(select(Adherent).offset(offset).limit(limit)).all()


@app.get("/adherents/{adherent_id}")
def get_adherent(
    adherent_id: int,
    session: SessionDep,
    response: Response,
    if_none_match: Annotated[str | None, Header()] = None,
):
    adherent = session.get(Adherent, adherent_id)
    if not adherent:
        raise HTTPException(status_code=404, detail=f"Adhérent avec l'identifiant {adherent_id} introuvable.")

    adherent_data = adherent.model_dump()
    etag = generate_etag(adherent_data)

    if if_none_match and if_none_match.strip() == etag:
        return Response(
            status_code=status.HTTP_304_NOT_MODIFIED,
            headers={
                "ETag": etag,
                "Cache-Control": "private, max-age=60",
            },
        )

    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "private, max-age=60"
    return adherent_data


@app.post("/adherents", status_code=status.HTTP_201_CREATED, response_model=Adherent)
def create_adherent(
    adherent_in: AdherentCreate,
    response: Response,
    session: SessionDep,
    _auth: AuthDep,
):
    existing = session.exec(select(Adherent).where(Adherent.email == adherent_in.email)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Un adhérent avec l'adresse email '{adherent_in.email}' existe déjà.",
        )

    adherent = Adherent.model_validate(adherent_in)
    session.add(adherent)
    session.commit()
    session.refresh(adherent)
    response.headers["Location"] = f"/adherents/{adherent.id}"
    return adherent


@app.patch("/adherents/{adherent_id}", response_model=Adherent)
def update_adherent(
    adherent_id: int,
    adherent_in: AdherentUpdate,
    session: SessionDep,
    _auth: AuthDep,
):
    adherent = session.get(Adherent, adherent_id)
    if not adherent:
        raise HTTPException(status_code=404, detail=f"Adhérent avec l'identifiant {adherent_id} introuvable.")

    data_to_update = adherent_in.model_dump(exclude_unset=True)
    if "email" in data_to_update and data_to_update["email"] != adherent.email:
        conflict = session.exec(select(Adherent).where(Adherent.email == data_to_update["email"])).first()
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"L'adresse email '{data_to_update['email']}' est déjà attribuée à un autre adhérent.",
            )

    for key, value in data_to_update.items():
        setattr(adherent, key, value)

    session.add(adherent)
    session.commit()
    session.refresh(adherent)
    return adherent


@app.delete("/adherents/{adherent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_adherent(
    adherent_id: int,
    session: SessionDep,
    _auth: AuthDep,
):
    adherent = session.get(Adherent, adherent_id)
    if not adherent:
        raise HTTPException(status_code=404, detail=f"Adhérent avec l'identifiant {adherent_id} introuvable.")
    session.delete(adherent)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ==========================================
# 9. Action Métier : Réservations
# ==========================================


@app.post(
    "/creneaux/{creneau_id}/reservations",
    status_code=status.HTTP_201_CREATED,
    response_model=Reservation,
)
def reserver_creneau(
    creneau_id: int,
    resa_in: ReservationCreate,
    response: Response,
    session: SessionDep,
    _auth: AuthDep,
):
    creneau = session.get(Creneau, creneau_id)
    if not creneau:
        raise HTTPException(status_code=404, detail=f"Créneau avec l'identifiant {creneau_id} introuvable.")

    adherent = session.get(Adherent, resa_in.adherent_id)
    if not adherent:
        raise HTTPException(status_code=404, detail=f"Adhérent avec l'identifiant {resa_in.adherent_id} introuvable.")

    existing_resa = session.exec(
        select(Reservation).where(
            Reservation.creneau_id == creneau_id,
            Reservation.adherent_id == resa_in.adherent_id,
        )
    ).first()
    if existing_resa:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cet adhérent est déjà inscrit à ce créneau.",
        )

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    reservation = Reservation(
        creneau_id=creneau_id,
        adherent_id=resa_in.adherent_id,
        statut="confirmee",
        cree_le=now_str,
    )
    session.add(reservation)

    creneau.places_prises = (creneau.places_prises or 0) + 1
    session.add(creneau)

    session.commit()
    session.refresh(reservation)

    response.headers["Location"] = f"/creneaux/{creneau_id}/reservations/{reservation.id}"
    return reservation