from typing import Annotated
from fastapi import Depends, FastAPI, HTTPException, Query
from sqlmodel import Field, Session, SQLModel, create_engine, select

app = FastAPI(title="API-Salle-de-Sport")

sqlite_file_name = "Salle-de-sport.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)

def get_session():
    with Session(engine) as session:
        yield session

SessionDep = Annotated[Session, Depends(get_session)]

# Modèle calqué sur le vrai schéma de ta table cours
class Cours(SQLModel, table=True):
    __tablename__ = "cours"

    id: int | None = Field(default=None, primary_key=True)
    type: str
    coach_id: int

@app.get("/")
def read_root():
    return {"message": "API Salle de Sport opérationnelle"}

@app.get("/cours")
def list_cours(
    session: SessionDep,
    offset: int = 0,
    limit: Annotated[int, Query(le=100)] = 20,
) -> list[Cours]:
    cours = session.exec(select(Cours).offset(offset).limit(limit)).all()
    return cours

@app.get("/cours/{cours_id}")
def get_cours(cours_id: int, session: SessionDep) -> Cours:
    cours = session.get(Cours, cours_id)
    if not cours:
        raise HTTPException(status_code=404, detail="Cours introuvable")
    return cours