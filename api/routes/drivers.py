from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.database import get_db
from api.schemas.drivers import DriverItem

router = APIRouter()

# Maps FastF1 CountryCode (ISO alpha-3 / custom) → (full nationality, flag emoji)
_NATIONALITY: dict[str, tuple[str, str]] = {
    "AUS": ("Australia", "🇦🇺"),
    "AUT": ("Austria", "🇦🇹"),
    "BEL": ("Belgium", "🇧🇪"),
    "BRA": ("Brazil", "🇧🇷"),
    "CAN": ("Canada", "🇨🇦"),
    "CHN": ("China", "🇨🇳"),
    "DNK": ("Denmark", "🇩🇰"),
    "FIN": ("Finland", "🇫🇮"),
    "FRA": ("France", "🇫🇷"),
    "GBR": ("Great Britain", "🇬🇧"),
    "GER": ("Germany", "🇩🇪"),
    "ITA": ("Italy", "🇮🇹"),
    "JPN": ("Japan", "🇯🇵"),
    "MEX": ("Mexico", "🇲🇽"),
    "MON": ("Monaco", "🇲🇨"),
    "NED": ("Netherlands", "🇳🇱"),
    "NZL": ("New Zealand", "🇳🇿"),
    "POL": ("Poland", "🇵🇱"),
    "ESP": ("Spain", "🇪🇸"),
    "SWE": ("Sweden", "🇸🇪"),
    "THA": ("Thailand", "🇹🇭"),
    "USA": ("United States", "🇺🇸"),
    "ARG": ("Argentina", "🇦🇷"),
    "RUS": ("Russia", "🇷🇺"),
}

# Constructor name → colour hex (authoritative; overrides whatever is in the DB)
_CONSTRUCTOR_COLORS: dict[str, str] = {
    "Red Bull": "#3671C6",
    "Ferrari": "#E8002D",
    "Mercedes": "#27F4D2",
    "McLaren": "#FF8000",
    "Aston Martin": "#229971",
    "Alpine": "#FF87BC",
    "Williams": "#64C4FF",
    "Racing Bulls": "#6692FF",
    "Haas": "#B6BABD",
    "Audi": "#52E252",
    "Cadillac": "#CC0000",
}


@router.get("/drivers", response_model=list[DriverItem])
def list_drivers(season: int, db: Session = Depends(get_db)) -> list[DriverItem]:
    rows = db.execute(
        text(
            """
            SELECT d.code, d.full_name, d.number, d.nationality,
                   c.name AS constructor_name, c.color_hex
            FROM drivers d
            JOIN driver_contracts dc ON dc.driver_id = d.id AND dc.season = :season
            JOIN constructors c ON c.id = dc.constructor_id
            ORDER BY d.code
            """
        ),
        {"season": season},
    ).fetchall()

    items: list[DriverItem] = []
    for row in rows:
        nat_code: str = row.nationality or ""
        nat_name, flag = _NATIONALITY.get(nat_code, (nat_code, "🏁"))
        constructor_name: str = row.constructor_name or ""
        color = _CONSTRUCTOR_COLORS.get(constructor_name, row.color_hex or "#6b7280")
        items.append(
            DriverItem(
                code=row.code,
                full_name=row.full_name,
                number=row.number,
                constructor=constructor_name,
                constructor_color=color,
                nationality=nat_name,
                flag=flag,
            )
        )
    return items
