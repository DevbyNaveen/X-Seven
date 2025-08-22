"""
Initialize the local SQLite database for development.
- Creates all tables from SQLAlchemy models
- Seeds a demo Business for testing dedicated chat
- Seeds 5 businesses per category (total 25) with detailed contact info,
  settings, and realistic menus/services so chat can query real data.

Usage:
    python3 db/init_dev_db.py
"""
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from typing import Dict, List, Optional

from app.config.database import Base, engine, SessionLocal
from app.models import (
    Business,
    SubscriptionPlan,
    PhoneNumberType,
    BusinessCategory,
    MenuCategory,
    MenuItem,
)  # noqa: F401


def _ensure_business(
    db: Session,
    *,
    name: str,
    slug: str,
    description: str,
    category: BusinessCategory,
    city: str = "Riga",
    country: str = "LV",
    phone: str = "+371 20000000",
    email: Optional[str] = None,
    website: Optional[str] = None,
    subscription: SubscriptionPlan = SubscriptionPlan.PRO,
) -> Business:
    b = db.query(Business).filter(Business.slug == slug).first()
    if b:
        return b
    contact_info: Dict[str, object] = {
        "address": f"{name} Street 1",
        "city": city,
        "country": country,
        "postal_code": "LV-1000",
        "phone": phone,
        "email": email or f"contact@{slug}.example",
        "website": website or f"https://{slug}.example",
        "whatsapp": phone,
        "hours": {
            "mon-fri": "08:00-20:00",
            "sat": "09:00-18:00",
            "sun": "10:00-16:00",
        },
        "location": {"lat": 56.9496, "lng": 24.1052},
    }
    settings: Dict[str, object] = {
        "supports_delivery": category == BusinessCategory.FOOD_HOSPITALITY,
        "supports_takeaway": category == BusinessCategory.FOOD_HOSPITALITY,
        "appointment_required": category != BusinessCategory.FOOD_HOSPITALITY,
        "multi_language": True,
    }
    b = Business(
        name=name,
        slug=slug,
        description=description,
        category=category,
        phone_config=PhoneNumberType.UNIVERSAL_ONLY,
        subscription_plan=subscription,
        is_active=True,
        contact_info=contact_info,
        settings=settings,
        branding_config={
            "primary_color": "#0ea5e9",
            "secondary_color": "#f59e0b",
            "logo_url": "https://picsum.photos/seed/" + slug + "/200/200",
        },
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    print(f"Seeded business: {slug}")
    return b


def _ensure_category(
    db: Session,
    *,
    business_id: int,
    name: str,
    description: str = "",
    display_order: int = 0,
    icon: Optional[str] = None,
) -> MenuCategory:
    c = (
        db.query(MenuCategory)
        .filter(MenuCategory.business_id == business_id, MenuCategory.name == name)
        .first()
    )
    if c:
        return c
    c = MenuCategory(
        business_id=business_id,
        name=name,
        description=description,
        display_order=display_order,
        icon=icon or "🍽️",
        is_active=True,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _ensure_item(
    db: Session,
    *,
    business_id: int,
    category_id: Optional[int],
    name: str,
    description: str,
    price: float,
    display_order: int = 0,
    available: bool = True,
    dietary_tags: Optional[List[str]] = None,
) -> MenuItem:
    i = (
        db.query(MenuItem)
        .filter(MenuItem.business_id == business_id, MenuItem.name == name)
        .first()
    )
    if i:
        return i
    i = MenuItem(
        business_id=business_id,
        category_id=category_id,
        name=name,
        description=description,
        base_price=price,
        is_available=available,
        display_order=display_order,
        dietary_tags=dietary_tags or [],
        allergens=[],
        stock_quantity=0,
    )
    db.add(i)
    db.commit()
    db.refresh(i)
    return i


def _seed_food_menu(db: Session, business: Business) -> None:
    beverages = _ensure_category(
        db, business_id=business.id, name="Beverages", description="Hot & cold drinks", display_order=1, icon="☕"
    )
    mains = _ensure_category(
        db, business_id=business.id, name="Mains", description="Main dishes", display_order=2, icon="🍝"
    )
    desserts = _ensure_category(
        db, business_id=business.id, name="Desserts", description="Sweet treats", display_order=3, icon="🍰"
    )
    starters = _ensure_category(
        db, business_id=business.id, name="Starters", description="Appetizers", display_order=0, icon="🥗"
    )

    # Beverages
    _ensure_item(db, business_id=business.id, category_id=beverages.id, name="Espresso", description="Rich espresso shot", price=2.5, display_order=1)
    _ensure_item(db, business_id=business.id, category_id=beverages.id, name="Cappuccino", description="Espresso with steamed milk foam", price=3.5, display_order=2)
    _ensure_item(db, business_id=business.id, category_id=beverages.id, name="Latte", description="Smooth espresso latte", price=3.8, display_order=3)
    _ensure_item(db, business_id=business.id, category_id=beverages.id, name="Green Tea", description="Freshly brewed", price=2.0, display_order=4)
    _ensure_item(db, business_id=business.id, category_id=beverages.id, name="Berry Smoothie", description="Mixed berries and yogurt", price=4.5, display_order=5)

    # Starters
    _ensure_item(db, business_id=business.id, category_id=starters.id, name="Garlic Bread", description="Toasted baguette with garlic butter", price=3.2, display_order=1)
    _ensure_item(db, business_id=business.id, category_id=starters.id, name="Fries", description="Crispy golden fries", price=2.9, display_order=2)

    # Mains
    _ensure_item(db, business_id=business.id, category_id=mains.id, name="Classic Burger", description="Beef patty, cheese, lettuce, tomato", price=8.9, display_order=1)
    _ensure_item(db, business_id=business.id, category_id=mains.id, name="Margherita Pizza", description="Tomato, mozzarella, basil", price=9.5, display_order=2)
    _ensure_item(db, business_id=business.id, category_id=mains.id, name="Caesar Salad", description="Romaine, parmesan, croutons", price=7.5, display_order=3)
    _ensure_item(db, business_id=business.id, category_id=mains.id, name="Pasta Carbonara", description="Creamy sauce with pancetta", price=10.5, display_order=4)

    # Desserts
    _ensure_item(db, business_id=business.id, category_id=desserts.id, name="Cheesecake", description="Classic baked cheesecake", price=4.2, display_order=1)
    _ensure_item(db, business_id=business.id, category_id=desserts.id, name="Croissant", description="Buttery French pastry", price=2.2, display_order=2)
    _ensure_item(db, business_id=business.id, category_id=desserts.id, name="Chocolate Muffin", description="Rich cocoa muffin", price=2.4, display_order=3)


def _seed_services_menu(db: Session, business: Business, services: List[Dict[str, object]]) -> None:
    category = _ensure_category(
        db, business_id=business.id, name="Services", description="Available services", display_order=1, icon="🛠️"
    )
    for idx, s in enumerate(services, start=1):
        _ensure_item(
            db,
            business_id=business.id,
            category_id=category.id,
            name=s["name"],
            description=str(s.get("description", "")),
            price=float(s.get("price", 0.0)),
            display_order=idx,
        )


def seed_demo_business(db: Session) -> None:
    existing = db.query(Business).filter(Business.slug == "demo-cafe").first()
    if not existing:
        demo = Business(
            name="Demo Cafe",
            slug="demo-cafe",
            description="Development demo business for testing",
            category=BusinessCategory.FOOD_HOSPITALITY,
            phone_config=PhoneNumberType.UNIVERSAL_ONLY,
            subscription_plan=SubscriptionPlan.BASIC,
            is_active=True,
            contact_info={"phone": "+371 20000001", "city": "Riga", "country": "LV"},
        )
        db.add(demo)
        db.commit()
        db.refresh(demo)
        _seed_food_menu(db, demo)
        print("Seeded demo Business: demo-cafe")
    else:
        print("Demo Business already present: demo-cafe")


def seed_full_dataset(db: Session) -> None:
    # Food & Hospitality (5)
    food_list = [
        ("Sunrise Cafe", "sunrise-cafe", "Cozy cafe for coffee & pastries"),
        ("Urban Eats", "urban-eats", "Casual dining with burgers and bowls"),
        ("Pasta Piazza", "pasta-piazza", "Fresh Italian pasta and pizzas"),
        ("Sushi Garden", "sushi-garden", "Modern sushi & Japanese kitchen"),
        ("Green Spoon", "green-spoon", "Healthy bowls, salads, smoothies"),
    ]
    for i, (name, slug, desc) in enumerate(food_list, start=1):
        b = _ensure_business(
            db,
            name=name,
            slug=slug,
            description=desc,
            category=BusinessCategory.FOOD_HOSPITALITY,
            phone=f"+371 20010{i:02d}",
            subscription=SubscriptionPlan.PRO,
        )
        _seed_food_menu(db, b)

    # Beauty & Personal Care (5)
    beauty_list = [
        ("Glow Salon", "glow-salon", "Hair & beauty studio"),
        ("Zen Spa", "zen-spa", "Relaxing spa treatments"),
        ("Barber Box", "barber-box", "Classic men's grooming"),
        ("Nail Artistry", "nail-artistry", "Manicures & pedicures"),
        ("Bliss Beauty Clinic", "bliss-beauty", "Cosmetic treatments"),
    ]
    beauty_services = [
        {"name": "Haircut", "price": 25.0, "description": "Women's/Men's haircut and style"},
        {"name": "Hair Color", "price": 60.0, "description": "Full color or highlights"},
        {"name": "Manicure", "price": 20.0, "description": "Classic manicure"},
        {"name": "Pedicure", "price": 25.0, "description": "Classic pedicure"},
        {"name": "Massage (60m)", "price": 45.0, "description": "Relaxation or deep tissue"},
    ]
    for i, (name, slug, desc) in enumerate(beauty_list, start=1):
        b = _ensure_business(
            db,
            name=name,
            slug=slug,
            description=desc,
            category=BusinessCategory.BEAUTY_PERSONAL_CARE,
            phone=f"+371 20020{i:02d}",
            subscription=SubscriptionPlan.PRO,
        )
        _seed_services_menu(db, b, beauty_services)

    # Automotive Services (5)
    auto_list = [
        ("QuickFix Auto", "quickfix-auto", "Repairs & maintenance"),
        ("Pro Wash", "pro-wash", "Car wash & detailing"),
        ("Brake Masters", "brake-masters", "Brake service specialists"),
        ("MotoCare", "moto-care", "Motorcycle service"),
        ("Auto Inspect", "auto-inspect", "Vehicle inspections"),
    ]
    auto_services = [
        {"name": "Oil Change", "price": 45.0, "description": "Synthetic oil & filter"},
        {"name": "Brake Service", "price": 120.0, "description": "Pads & inspection"},
        {"name": "Tire Rotation", "price": 25.0, "description": "Rotate & pressure check"},
        {"name": "Detailing", "price": 80.0, "description": "Interior & exterior"},
        {"name": "Inspection", "price": 35.0, "description": "Annual technical check"},
    ]
    for i, (name, slug, desc) in enumerate(auto_list, start=1):
        b = _ensure_business(
            db,
            name=name,
            slug=slug,
            description=desc,
            category=BusinessCategory.AUTOMOTIVE_SERVICES,
            phone=f"+371 20030{i:02d}",
            subscription=SubscriptionPlan.BASIC,
        )
        _seed_services_menu(db, b, auto_services)

    # Health & Medical (5)
    health_list = [
        ("Sunrise Clinic", "sunrise-clinic", "Family healthcare"),
        ("Bright Dental", "bright-dental", "Dental care"),
        ("VetCare", "vetcare", "Veterinary clinic"),
        ("Wellness Center", "wellness-center", "Physio & wellness"),
        ("UrgentCare", "urgentcare", "Walk-in urgent care"),
    ]
    health_services = [
        {"name": "General Checkup", "price": 40.0, "description": "Routine examination"},
        {"name": "Dental Cleaning", "price": 55.0, "description": "Cleaning & polish"},
        {"name": "Vaccination", "price": 20.0, "description": "Common vaccines"},
        {"name": "Physiotherapy (45m)", "price": 50.0, "description": "Rehab & therapy"},
        {"name": "Emergency Visit", "price": 75.0, "description": "Walk-in urgent care"},
    ]
    for i, (name, slug, desc) in enumerate(health_list, start=1):
        b = _ensure_business(
            db,
            name=name,
            slug=slug,
            description=desc,
            category=BusinessCategory.HEALTH_MEDICAL,
            phone=f"+371 20040{i:02d}",
            subscription=SubscriptionPlan.ENTERPRISE,
        )
        _seed_services_menu(db, b, health_services)

    # Local Services (5)
    local_list = [
        ("Sparkle Clean", "sparkle-clean", "Home cleaning"),
        ("Happy Paws", "happy-paws", "Pet care & grooming"),
        ("GreenThumb", "green-thumb", "Lawn & garden care"),
        ("TutorNow", "tutor-now", "Tutoring services"),
        ("RepairPro", "repair-pro", "Home repair & handyman"),
    ]
    local_services = [
        {"name": "House Cleaning (2h)", "price": 35.0, "description": "Two-hour cleaning"},
        {"name": "Pet Grooming", "price": 30.0, "description": "Wash & trim"},
        {"name": "Lawn Mowing", "price": 25.0, "description": "Up to 500 m²"},
        {"name": "Math Tutoring (1h)", "price": 20.0, "description": "High school level"},
        {"name": "Handyman Hour", "price": 28.0, "description": "General repairs"},
    ]
    for i, (name, slug, desc) in enumerate(local_list, start=1):
        b = _ensure_business(
            db,
            name=name,
            slug=slug,
            description=desc,
            category=BusinessCategory.LOCAL_SERVICES,
            phone=f"+371 20050{i:02d}",
            subscription=SubscriptionPlan.BASIC,
        )
        _seed_services_menu(db, b, local_services)

    print("Full dataset seeding complete (idempotent).")


def init_db() -> None:
    # Ensure all tables exist
    Base.metadata.create_all(bind=engine)

    # Seed dataset
    db = SessionLocal()
    try:
        seed_demo_business(db)
        seed_full_dataset(db)
    finally:
        db.close()


if __name__ == "__main__":
    try:
        init_db()
        print("Database initialized successfully.")
    except OperationalError as e:
        print("Database initialization failed:", e)
        raise
