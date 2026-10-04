"""
Seed script for Phase 1.
Run this ONCE to create the database, tables, and insert default
users, stations, and assets.
"""
import sys
import os

# Add the server root to PYTHONPATH so we can import src.*
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.db.database import Base, engine, SessionLocal
from src.db.models import User, Station, UserStationAccess, Asset, SystemSettings
from src.services.auth_service import hash_password
from src.services.operational_service import ensure_operational_seed


def seed_database():
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        if db.query(User).first():
            # Keep demo accounts available when an existing database predates
            # the complete frontend account list.
            stations = {station.id: station for station in db.query(Station).all()}
            demo_users = [
                ("maint@ncpor.in", "Maintenance User", "maintenance", "bharati"),
                ("logistics@ncpor.in", "Logistics User", "logistics", "maitri"),
            ]
            for email, name, role, station_id in demo_users:
                user = db.query(User).filter(User.email == email).first()
                if not user:
                    user = User(
                        email=email,
                        name=name,
                        role=role,
                        password_hash=hash_password("antarctic"),
                    )
                    db.add(user)
                    db.flush()
                if station_id in stations and not any(
                    access.station_id == station_id for access in user.station_access
                ):
                    db.add(UserStationAccess(user_id=user.id, station_id=station_id))
            db.commit()
            ensure_operational_seed(db)
            print("Database already seeded. Operational records verified.")
            return

        print("Seeding Users...")
        # Create users matching the old frontend expectations
        admin = User(
            email="admin@ncpor.res.in",
            name="Admin User",
            role="admin",
            password_hash=hash_password("antarctic"),
        )
        ops = User(
            email="ops@ncpor.res.in",
            name="Operations User",
            role="ops",
            password_hash=hash_password("antarctic"),
        )
        maint = User(
            email="maint@ncpor.in",
            name="Maintenance User",
            role="maintenance",
            password_hash=hash_password("antarctic"),
        )
        logistics = User(
            email="logistics@ncpor.in",
            name="Logistics User",
            role="logistics",
            password_hash=hash_password("antarctic"),
        )
        db.add_all([admin, ops, maint, logistics])
        db.commit()

        print("Seeding Stations...")
        maitri = Station(id="maitri", name="Maitri", latitude=-70.76, longitude=11.73, established_year=1989)
        bharati = Station(id="bharati", name="Bharati", latitude=-69.40, longitude=76.19, established_year=2012)
        db.add_all([maitri, bharati])
        db.commit()

        print("Seeding User-Station Access...")
        usa1 = UserStationAccess(user_id=admin.id, station_id=maitri.id)
        usa2 = UserStationAccess(user_id=admin.id, station_id=bharati.id)
        usa3 = UserStationAccess(user_id=ops.id, station_id=maitri.id)
        usa4 = UserStationAccess(user_id=maint.id, station_id=bharati.id)
        usa5 = UserStationAccess(user_id=logistics.id, station_id=maitri.id)
        db.add_all([usa1, usa2, usa3, usa4, usa5])
        db.commit()

        print("Seeding Assets...")
        # Copying asset layout from simulation so we have it persisted
        _ASSET_DEFS = [
            ("gen1",   "Generator 01",    "generator",  6,  4,  16,  9, ["bat"], 30),
            ("gen2",   "Generator 02",    "generator",  6,  16, 16,  9, ["bat"], 30),
            ("gen3",   "Generator 03",    "generator",  6,  28, 16,  9, ["bat"], 30),
            ("fuel",   "Fuel Tank Farm",  "fuel",       6,  41, 16,  9, ["gen1", "gen2", "gen3"], 0),
            ("bat",    "Battery Bank",    "battery",    34,  4, 16, 10, ["heat", "living", "lab", "comms", "water"], 0),
            ("heat",   "Heating Plant",   "heating",    34, 20, 16, 10, [], 0),
            ("water",  "Water Plant",     "water",      34, 36, 16, 10, [], 0),
            ("living", "Living Module",   "living",     62,  4, 18, 12, [], 0),
            ("lab",    "Science Lab",     "lab",        62, 22, 18, 12, [], 0),
            ("comms",  "Comms Hub",       "comms",      62, 40, 18, 10, [], 0),
        ]

        assets = []
        for st_id in ["maitri", "bharati"]:
            for key, name, atype, x, y, w, h, links, cap in _ASSET_DEFS:
                assets.append(Asset(
                    station_id=st_id,
                    asset_key=key,
                    name=name,
                    type=atype,
                    x=x, y=y, w=w, h=h,
                    links=links,
                    capacity_kw=cap,
                    operational_hours=1500, # Initial seed
                    last_service_date="2026-09-01",
                    next_service_date="2026-11-01",
                ))
        db.add_all(assets)
        db.commit()

        print("Seeding Settings...")
        settings_maitri = SystemSettings(station_id="maitri")
        settings_bharati = SystemSettings(station_id="bharati")
        db.add_all([settings_maitri, settings_bharati])
        db.commit()

        ensure_operational_seed(db)

        print("Seed complete! DB is ready.")

if __name__ == "__main__":
    seed_database()
