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


@router.get("/drivers", response_model=list[DriverItem])
def list_drivers(
    season: int,
    round: int | None = None,
    db: Session = Depends(get_db),
) -> list[DriverItem]:
    rows = db.execute(
        text(
            """
            SELECT d.code, d.full_name, d.number, d.nationality,
                   c.name AS constructor_name, c.color_hex
            FROM drivers d
            JOIN driver_contracts dc ON dc.driver_id = d.id AND dc.season = :season
            JOIN constructors c ON c.id = dc.constructor_id
            WHERE
                (:round IS NULL AND dc.end_round IS NULL)
                OR (
                    :round IS NOT NULL
                    AND dc.start_round <= :round
                    AND (dc.end_round IS NULL OR dc.end_round >= :round)
                )
            ORDER BY d.code
            """
        ),
        {"season": season, "round": round},
    ).fetchall()

    items: list[DriverItem] = []
    for row in rows:
        nat_code: str = row.nationality or ""
        nat_name, flag = _NATIONALITY.get(nat_code, (nat_code, "🏁"))
        items.append(
            DriverItem(
                code=row.code,
                full_name=row.full_name,
                number=row.number,
                constructor=row.constructor_name,
                constructor_color=row.color_hex or "#6b7280",
                nationality=nat_name,
                flag=flag,
            )
        )
    return items
