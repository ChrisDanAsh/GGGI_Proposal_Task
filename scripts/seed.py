# Ten realistic proposals, inserted idempotently. Without this, whoever
# opens the app first sees an empty table and two dropdowns that appear
# to do nothing - these ten spread across eight countries and four of
# the five categories so that filtering is demonstrably doing something,
# and give a screen recording something to show in its first five
# seconds.
#
# Run with `python -m scripts.seed`.

from app.db.repository import ProposalRepository
from app.db.session import SessionLocal
from app.schemas.proposal import ProposalCreate
from app.services.proposal import create_proposal

# Fixed here, not generated, so the demo and any README screenshots are
# reproducible. Every country code below must be a real GGGI member -
# checked against app/domain/data/gggi_members.txt rather than assumed,
# since a plausible-looking code (India, for instance) can still be
# wrong. Start dates are in 2026, forward of this document's date, so
# the data reads as a live pipeline rather than a historical archive;
# one entry has no start date at all, exercising that optional field on
# both the list and detail pages.
#
# Countries: KE x2, ET x2, RW, VN, ID, PH, MN, PE - eight distinct
# countries, two repeated so filtering by country visibly returns more
# than one row rather than a coincidence. Categories: renewable_energy
# x4, climate_risk_mapping x3, smart_grid x2, mrv x1 - "other" is
# deliberately unused, so filtering by it demonstrates the empty state.
SEED_PROPOSALS: list[dict[str, object]] = [
    {
        "project_name": "Lake Turkana Solar Mini-Grid Expansion",
        "country": "KE",
        "category": "renewable_energy",
        "budget_usd": "2450000.00",
        "start_date": "2026-03-01",
        "summary": (
            "Expands the existing Lake Turkana mini-grid with an "
            "additional 8 MW of solar generation and battery storage, "
            "extending reliable electricity to twelve pastoralist "
            "communities across Marsabit County."
        ),
    },
    {
        "project_name": "Nairobi Distribution Network Smart Metering",
        "country": "KE",
        "category": "smart_grid",
        "budget_usd": "1180000.00",
        "start_date": "2026-05-15",
        "summary": (
            "Deploys 40,000 smart meters across three Nairobi "
            "distribution substations, giving the utility real-time "
            "load visibility and giving customers usage data to reduce "
            "peak-hour consumption."
        ),
    },
    {
        "project_name": "Rift Valley Flood Exposure Atlas",
        "country": "ET",
        "category": "climate_risk_mapping",
        "budget_usd": "640000.00",
        "start_date": "2026-01-20",
        "summary": (
            "Produces a high-resolution flood exposure atlas for the "
            "Ethiopian Rift Valley, combining satellite rainfall data "
            "with settlement mapping to guide district-level "
            "early-warning planning."
        ),
    },
    {
        "project_name": "Addis Ababa Industrial Emissions MRV Platform",
        "country": "ET",
        "category": "mrv",
        "budget_usd": "890000.00",
        "start_date": None,
        "summary": (
            "Builds a continuous emissions monitoring, reporting, and "
            "verification platform for forty industrial facilities in "
            "the Addis Ababa corridor, replacing annual paper audits "
            "with real-time sensor data."
        ),
    },
    {
        "project_name": "Kigali Rooftop Solar Cooperative",
        "country": "RW",
        "category": "renewable_energy",
        "budget_usd": "375000.00",
        "start_date": "2026-07-01",
        "summary": (
            "Finances a rooftop solar cooperative across 600 households "
            "and small workshops in Kigali, pooling purchasing power to "
            "cut per-household installation cost by roughly a third."
        ),
    },
    {
        "project_name": "Mekong Delta Saltwater Intrusion Mapping",
        "country": "VN",
        "category": "climate_risk_mapping",
        "budget_usd": "1520000.00",
        "start_date": "2026-02-10",
        "summary": (
            "Maps seasonal saltwater intrusion across the Mekong "
            "Delta's rice-growing provinces using river-mouth sensors "
            "and satellite salinity data, informing planting-calendar "
            "adjustments for smallholder farmers."
        ),
    },
    {
        "project_name": "Java Geothermal Wellhead Pilot",
        "country": "ID",
        "category": "renewable_energy",
        "budget_usd": "4300000.00",
        "start_date": "2026-09-01",
        "summary": (
            "Pilots a 5 MW wellhead geothermal unit on an underused "
            "exploration well in West Java, testing a lower-cost "
            "deployment model that could unlock dozens of similar "
            "stranded wells across the archipelago."
        ),
    },
    {
        "project_name": "Luzon Typhoon Grid Resilience Upgrade",
        "country": "PH",
        "category": "smart_grid",
        "budget_usd": "2760000.00",
        "start_date": "2026-04-05",
        "summary": (
            "Upgrades transmission towers and adds automated "
            "sectionalising switches across a typhoon-exposed Luzon "
            "corridor, cutting average storm-related outage duration "
            "for an estimated 200,000 customers."
        ),
    },
    {
        "project_name": "Gobi Desert Utility-Scale Solar Corridor",
        "country": "MN",
        "category": "renewable_energy",
        "budget_usd": "3100000.00",
        "start_date": "2026-06-12",
        "summary": (
            "Develops a 150 MW utility-scale solar corridor across "
            "degraded Gobi Desert grazing land unsuitable for "
            "livestock, feeding Mongolia's central grid and displacing "
            "diesel-fired peaking capacity currently used to cover "
            "winter demand spikes in the capital region, with a "
            "buffer for dust storms."
        ),
    },
    {
        "project_name": "Andean Glacier Retreat Monitoring Network",
        "country": "PE",
        "category": "climate_risk_mapping",
        "budget_usd": "725000.00",
        "start_date": "2026-08-18",
        "summary": (
            "Installs automated monitoring stations on retreating "
            "Andean glaciers feeding Lima's water supply, providing "
            "early data on meltwater trends for long-term municipal "
            "water security planning."
        ),
    },
]


def main() -> None:
    # Manages its own session rather than borrowing get_db(), which is a
    # request-scoped generator dependency and is not meaningful outside
    # an actual HTTP request.
    db = SessionLocal()
    try:
        repo = ProposalRepository(db)
        created = 0
        for entry in SEED_PROPOSALS:
            # Idempotent by name check: the container entrypoint runs
            # this on every start (Module 16), so running it twice must
            # be harmless rather than raising a duplicate-name error or
            # doubling the table.
            if repo.exists_with_name(entry["project_name"]):
                continue
            # Goes through ProposalCreate and create_proposal, never
            # straight to db.add(Proposal(...)) - the seed data is
            # therefore validated by the exact same rules a person's
            # submission faces, so a typo above (a bad country code, an
            # oversized summary) fails loudly here instead of silently
            # inserting a row the rest of the application considers
            # invalid.
            data = ProposalCreate(**entry)
            create_proposal(data, repo)
            created += 1
        db.commit()
        # The confirmation, visible in `docker compose up`'s logs, that
        # the database was actually populated.
        print(
            f"Seed complete: {created} created, "
            f"{len(SEED_PROPOSALS) - created} already present."
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
