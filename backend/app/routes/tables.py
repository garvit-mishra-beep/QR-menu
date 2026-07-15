from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import crud, schemas

router = APIRouter(prefix="/tables", tags=["Tables"])

@router.get("", response_model=List[schemas.TableResponse])
def get_all_tables(db: Session = Depends(get_db)):
    """
    Retrieve all active tables with their numbers and QR code links.
    """
    return crud.get_tables(db)
