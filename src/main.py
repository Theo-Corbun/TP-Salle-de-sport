from typing import Annotated, Any
from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlmodel import Field, Session, SQLModel, create_engine, func, select

app = FastAPI(title="API Salle de Sport")

sqlite_file_name = "Salle-de-sport.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"
connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


# ==========================================
# Modèles SQLModel (Tables)
# ==========================================


class Cours(SQLModel, table=True):
    __tablename__ = "cours"
    id: int | None = Field(default=None, primary_key=True)
    type: str
    coach_id: int


class CoursCreate(BaseModel):
    type: str
    coach_id: int


class CoursUpdate(BaseModel):
    type: str | None = None
    coach_id: int | None = None


class Adherent(SQLModel, table=True):
    __tablename__ = "adherents"
    id: int | None = Field(default=None, primary_key=True)
    nom: str
    email: str
    telephone: str | None = None


class AdherentCreate(BaseModel):
    nom: str
    email: str
    telephone: str | None = None


class AdherentUpdate(BaseModel):
    nom: str | None = None
    email: str | None = None
    telephone: str | None = None


# ==========================================
# Modèle d'enveloppe de réponse paginée
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


# ==========================================
# 1. Ressource : Cours (Collection Navigable + CRUD)
# ==========================================


@app.get("/cours", response_model=PagedResponse)
def list_cours(
    session: SessionDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    type: str | None = None,
    tri: str = Query(default="asc", pattern="^(asc|desc)$"),
):
    # Requête de base
    statement = select(Cours)

    # Filtrage optionnel
    if type:
        statement = statement.where(Cours.type.ilike(f"%{type}%"))

    # Calcul du total filtré
    count_statement = select(func.count()).select_from(statement.subquery())
    total = session.exec(count_statement).one()

    # Tri stable (clé secondaire 'id' pour éviter les dérives)
    if tri == "desc":
        statement = statement.order_by(Cours.type.desc(), Cours.id.desc())
    else:
        statement = statement.order_by(Cours.type.asc(), Cours.id.asc())

    # Pagination offset
    items = session.exec(statement.offset(offset).limit(limit)).all()

    # Liens hypertextes (touche niveau 3)
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


@app.get("/cours/{cours_id}", response_model=Cours)
def get_cours(cours_id: int, session: SessionDep):
    cours = session.get(Cours, cours_id)
    if not cours:
        raise HTTPException(status_code=404, detail="Cours introuvable")
    return cours


@app.post(
    "/cours", status_code=status.HTTP_201_CREATED, response_model=Cours
)
def create_cours(
    cours_in: CoursCreate, response: Response, session: SessionDep
):
    cours = Cours.model_validate(cours_in)
    session.add(cours)
    session.commit()
    session.refresh(cours)
    # En-tête Location obligatoire pour un 201 Created
    response.headers["Location"] = f"/cours/{cours.id}"
    return cours


@app.patch("/cours/{cours_id}", response_model=Cours)
def update_cours(
    cours_id: int, cours_in: CoursUpdate, session: SessionDep
):
    cours = session.get(Cours, cours_id)
    if not cours:
        raise HTTPException(status_code=404, detail="Cours introuvable")

    data_to_update = cours_in.model_dump(exclude_unset=True)
    for key, value in data_to_update.items():
        setattr(cours, key, value)

    session.add(cours)
    session.commit()
    session.refresh(cours)
    return cours


@app.delete("/cours/{cours_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cours(cours_id: int, session: SessionDep):
    cours = session.get(Cours, cours_id)
    if not cours:
        raise HTTPException(status_code=404, detail="Cours introuvable")
    session.delete(cours)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ==========================================
# 2. Ressource : Adherents (CRUD complet)
# ==========================================


@app.get("/adherents", response_model=list[Adherent])
def list_adherents(
    session: SessionDep,
    offset: int = 0,
    limit: Annotated[int, Query(le=100)] = 20,
):
    return session.exec(select(Adherent).offset(offset).limit(limit)).all()


@app.get("/adherents/{adherent_id}", response_model=Adherent)
def get_adherent(adherent_id: int, session: SessionDep):
    adherent = session.get(Adherent, adherent_id)
    if not adherent:
        raise HTTPException(status_code=404, detail="Adhérent introuvable")
    return adherent


@app.post(
    "/adherents", status_code=status.HTTP_201_CREATED, response_model=Adherent
)
def create_adherent(
    adherent_in: AdherentCreate, response: Response, session: SessionDep
):
    adherent = Adherent.model_validate(adherent_in)
    session.add(adherent)
    session.commit()
    session.refresh(adherent)
    response.headers["Location"] = f"/adherents/{adherent.id}"
    return adherent


@app.patch("/adherents/{adherent_id}", response_model=Adherent)
def update_adherent(
    adherent_id: int, adherent_in: AdherentUpdate, session: SessionDep
):
    adherent = session.get(Adherent, adherent_id)
    if not adherent:
        raise HTTPException(status_code=404, detail="Adhérent introuvable")

    data_to_update = adherent_in.model_dump(exclude_unset=True)
    for key, value in data_to_update.items():
        setattr(adherent, key, value)

    session.add(adherent)
    session.commit()
    session.refresh(adherent)
    return adherent


@app.delete("/adherents/{adherent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_adherent(adherent_id: int, session: SessionDep):
    adherent = session.get(Adherent, adherent_id)
    if not adherent:
        raise HTTPException(status_code=404, detail="Adhérent introuvable")
    session.delete(adherent)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)