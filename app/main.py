import os
import asyncio
from datetime import datetime, date
from fastapi import FastAPI, Depends, Query, Request, Header, HTTPException, Form, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from .db import Base, engine, get_db
from .models import Item, Ad, ServiceOffer, LocalBusiness, AdRequest
from .ranking import KEYWORDS
from scripts.ingest import ingest

Base.metadata.create_all(bind=engine)

app = FastAPI(title="LocalBrain API", version="0.1.0")
templates = Jinja2Templates(directory="app/templates")

# Serve static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Scheduler per ingest automatico
scheduler = AsyncIOScheduler()
scheduler.add_job(
    ingest,
    trigger=CronTrigger(minute="0"),  # Esegue ogni ora
    id="hourly_ingest",
    replace_existing=True
)

SERVICE_CATEGORIES = [
    ("pulizie", "Pulizie domestiche"),
    ("babysitter", "Babysitter"),
    ("dogsitter", "Dog sitter"),
    ("assistenza", "Assistenza anziani"),
    ("ripetizioni", "Ripetizioni e lezioni"),
    ("manutenzione", "Manutenzioni e piccoli lavori"),
    ("eventi", "Supporto eventi"),
    ("altro", "Altro"),
]
OFFER_STATUSES = ["pending", "published", "archived", "rejected"]

BUSINESS_CATEGORIES = [
    ("servizi", "Servizi Locali"),
    ("ristorazione", "Bar e Ristorazione"),
    ("wellness", "Benessere"),
    ("professionisti", "Professionisti"),
    ("negozi", "Negozi"),
    ("turismo", "Turismo"),
    ("altro", "Altro"),
]

@app.on_event("startup")
async def startup_event():
    """Avvia lo scheduler all'avvio dell'app"""
    scheduler.start()
    print("✅ Scheduler avviato - ingest automatico ogni ora")

@app.on_event("shutdown")
def shutdown_event():
    """Ferma lo scheduler alla chiusura"""
    scheduler.shutdown()
    print("❌ Scheduler fermato")

@app.get("/")
def root():
    """Redirect root to dashboard"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/dashboard")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/admin/ingest-now")
async def ingest_now():
    """Trigger manuale per ingest"""
    try:
        await ingest()
        return {"status": "success", "message": "Ingest completato"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/items")
def list_items(
    city: str | None = Query(None),
    category: str | None = Query(None),
    limit: int = 50,
    include_ads: bool = Query(False),
    every: int = Query(3, ge=1),
    db: Session = Depends(get_db)
):
    q = db.query(Item).order_by(Item.published_at.desc())
    if city:
        q = q.filter(Item.city.ilike(f"%{city}%"))
    if category:
        q = q.filter(Item.category == category)
    items = [{
        "type": "item",
        "id": i.id,
        "title": i.title,
        "url": i.url,
        "summary": i.summary,
        "source": i.source,
        "city": i.city,
        "category": i.category,
        "published_at": i.published_at.isoformat() if i.published_at else None,
        "score": i.score,
        "image_url": i.image_url
    } for i in q.limit(limit).all()]

    if not include_ads or not items:
        return items

    ads = (
        db.query(Ad)
        .filter(Ad.active == True, Ad.show_in_feed == True)
        .order_by(Ad.created_at.desc())
        .all()
    )
    if not ads:
        return items

    enriched = []
    ad_index = 0
    for idx, it in enumerate(items, start=1):
        enriched.append(it)
        if idx % every == 0:
            ad = ads[ad_index % len(ads)]
            enriched.append({
                "type": "ad",
                "title": ad.title,
                "url": ad.url,
                "message": ad.message,
                "sponsor": True,
                "category": ad.category,
                "city": ad.city,
                "image_url": ad.image_url,
            })
            ad_index += 1
    return enriched

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    city: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    q = db.query(Item).order_by(Item.published_at.desc())
    if city:
        q = q.filter(Item.city.ilike(f"%{city}%"))
    if category:
        q = q.filter(Item.category == category)
    raw_items = q.limit(limit).all()

    all_ads = db.query(Ad).filter(Ad.active == True).order_by(Ad.created_at.desc()).all()

    ads = [ad for ad in all_ads if ad.show_in_feed]
    every = max(int(os.getenv("FEED_AD_FREQUENCY", "3") or 3), 1)

    combined = []
    ad_index = 0
    for idx, item in enumerate(raw_items, start=1):
        combined.append({"type": "item", "record": item})
        if ads and idx % every == 0:
            combined.append({"type": "ad", "record": ads[ad_index % len(ads)]})
            ad_index += 1

    city_rows = db.query(Item.city).distinct().all()
    available_cities = sorted({row[0] for row in city_rows if row[0]})
    categories = sorted({*KEYWORDS.keys(), "altro"})

    def summarize(text: Optional[str], max_length: int = 320) -> str:
        if not text:
            return ""
        stripped = text.strip()
        if len(stripped) <= max_length:
            return stripped
        truncated = stripped[:max_length].rsplit(" ", 1)[0]
        return f"{truncated}…"

    items_view = []
    for entry in combined:
        if entry["type"] == "item":
            i = entry["record"]
            items_view.append({
                "type": "item",
                "id": i.id,
                "title": i.title,
                "url": i.url,
                "summary": summarize(i.summary),
                "source": i.source,
                "city": i.city,
                "category": i.category,
                "published_at": i.published_at.strftime("%d/%m/%Y %H:%M") if i.published_at else "",
                "image_url": i.image_url,
            })
        else:
            ad = entry["record"]
            items_view.append({
                "type": "ad",
                "title": ad.title,
                "url": ad.url,
                "message": ad.message,
                "category": ad.category,
                "city": ad.city,
                "image_url": ad.image_url,
            })

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "featured_offers": [_serialize_offer(o) for o in _get_highlighted_offers(db)],
            "items": items_view,
            "cities": available_cities,
            "categories": categories,
            "selected_city": city or "",
            "selected_category": category or "",
            "limit": limit,
            "generated_at": datetime.utcnow().strftime("%d/%m/%Y %H:%M"),
            "sidebar_ads": _build_sidebar_ads(all_ads),
        }
    )




def _serialize_business(biz: LocalBusiness) -> dict:
    return {
        "id": biz.id,
        "name": biz.name,
        "description": biz.description,
        "category": biz.category,
        "category_label": dict(BUSINESS_CATEGORIES).get(biz.category, biz.category.title()),
        "address": biz.address,
        "city": biz.city,
        "contact_name": biz.contact_name,
        "contact_phone": biz.contact_phone,
        "contact_email": biz.contact_email,
        "website": biz.website,
        "social_link": biz.social_link,
        "image_url": biz.image_url,
        "highlighted": biz.highlighted,
        "created_at": biz.created_at.isoformat() if biz.created_at else None,
    }
def _serialize_offer(offer: ServiceOffer) -> dict:
    return {
        "id": offer.id,
        "title": offer.title,
        "description": offer.description,
        "category": offer.category,
        "category_label": dict(SERVICE_CATEGORIES).get(offer.category, offer.category.title()),
        "city": offer.city,
        "zone": offer.zone,
        "contact_name": offer.contact_name,
        "contact_method": offer.contact_method,
        "rate": offer.rate,
        "available_from": offer.available_from.isoformat() if offer.available_from else None,
        "available_to": offer.available_to.isoformat() if offer.available_to else None,
        "available_range": _format_range(offer.available_from, offer.available_to),
        "status": offer.status,
        "highlighted": offer.highlighted,
        "created_at": offer.created_at.isoformat() if offer.created_at else None,
    }

def _get_highlighted_offers(db: Session, limit: int = 3):
    return (
        db.query(ServiceOffer)
        .filter(ServiceOffer.status == "published")
        .order_by(ServiceOffer.highlighted.desc(), ServiceOffer.created_at.desc())
        .limit(limit)
        .all()
    )
def _build_sidebar_ads(all_ads: list[Ad]):
    def serialize(ad: Ad | None):
        if not ad:
            return None
        return {
            "title": ad.title,
            "url": ad.url,
            "message": ad.message,
            "category": ad.category,
            "city": ad.city,
            "image_url": ad.image_url,
        }

    left = next((ad for ad in all_ads if (ad.sidebar_slot or "").lower() == "left"), None)
    right = next((ad for ad in all_ads if (ad.sidebar_slot or "").lower() == "right"), None)
    fallback = [ad for ad in all_ads if (ad.sidebar_slot or "").lower() not in {"left", "right"}]
    if not left and fallback:
        left = fallback.pop(0)
    if not right and fallback:
        right = fallback.pop(0)
    return {
        "left": serialize(left),
        "right": serialize(right),
    }


def _format_range(start: date | None, end: date | None) -> str:
    if start and end:
        return f'{start.isoformat()} → {end.isoformat()}'
    if start:
        return f'dal {start.isoformat()}'
    if end:
        return f'fino al {end.isoformat()}'
    return ''
def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _check_admin(admin_token_header: str | None, env_token: str):
    if not env_token:
        # Se non è impostato ADMIN_TOKEN, l'accesso è libero.
        return
    if not admin_token_header or admin_token_header != env_token:
        raise HTTPException(status_code=401, detail="Token admin mancante o non valido")

@app.get("/admin/ads", response_class=HTMLResponse)
def ads_admin(
    request: Request,
    token: str | None = Query(None),
):
    env_token = os.getenv("ADMIN_TOKEN", "")
    requires_token = bool(env_token)
    if requires_token:
        _check_admin(token, env_token)
    else:
        token = ""
    return templates.TemplateResponse(
        "ads_admin.html",
        {
            "request": request,
            "admin_token": token or "",
            "requires_token": requires_token,
        },
    )

@app.get("/ads")
def list_ads(active: bool | None = Query(None), db: Session = Depends(get_db)):
    q = db.query(Ad)
    if active is not None:
        q = q.filter(Ad.active == active)
    return [{
        "id": a.id,
        "title": a.title,
        "url": a.url,
        "message": a.message,
        "category": a.category,
        "city": a.city,
        "active": a.active,
        "weight": a.weight,
        "show_in_feed": a.show_in_feed,
        "sidebar_slot": a.sidebar_slot,
        "image_url": a.image_url,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    } for a in q.order_by(Ad.created_at.desc()).all()]

@app.post("/ads")
def create_ad(
    title: str = Query(...),
    url: str = Query(...),
    message: str = Query(""),
    category: str = Query("all"),
    city: str = Query("all"),
    active: bool = Query(True),
    weight: float = Query(1.0),
    show_in_feed: bool = Query(True),
    sidebar_slot: str = Query(""),
    image_url: str = Query(""),
    admin_token: str | None = Header(None, alias="X-Admin-Token"),
    db: Session = Depends(get_db)
):
    env_token = os.getenv("ADMIN_TOKEN", "")
    _check_admin(admin_token, env_token)
    slot = (sidebar_slot or "").lower()
    if slot not in {"left", "right"}:
        slot = ""
    ad = Ad(
        title=title,
        url=url,
        message=message,
        category=category,
        city=city,
        active=active,
        weight=weight,
        show_in_feed=show_in_feed,
        sidebar_slot=slot,
        image_url=image_url,
    )
    db.add(ad)
    db.commit()
    db.refresh(ad)
    return {"status": "ok", "id": ad.id}

@app.delete("/ads/{ad_id}")
def delete_ad(
    ad_id: int,
    admin_token: str | None = Header(None, alias="X-Admin-Token"),
    db: Session = Depends(get_db)
):
    env_token = os.getenv("ADMIN_TOKEN", "")
    _check_admin(admin_token, env_token)
    ad = db.query(Ad).filter(Ad.id == ad_id).first()
    if not ad:
        raise HTTPException(status_code=404, detail="Ad non trovato")
    db.delete(ad)
    db.commit()
    return {"status": "ok"}


@app.get("/offers", response_class=HTMLResponse)
def offers_page(
    request: Request,
    city: str | None = Query(None),
    category: str | None = Query(None),
    submitted: bool = Query(False),
    db: Session = Depends(get_db)
):
    q = db.query(ServiceOffer).filter(ServiceOffer.status == "published").order_by(ServiceOffer.created_at.desc())
    if city:
        q = q.filter(ServiceOffer.city.ilike(f"%{city}%"))
    if category and category != "tutte":
        q = q.filter(ServiceOffer.category == category)
    offers = q.all()

    cities = sorted({row[0] for row in db.query(ServiceOffer.city).distinct() if row[0]})
    zone_options = sorted({row[0] for row in db.query(ServiceOffer.zone).distinct() if row[0]})

    return templates.TemplateResponse(
        "offers.html",
        {
            "request": request,
            "offers": [_serialize_offer(o) for o in offers],
            "categories": SERVICE_CATEGORIES,
            "selected_category": category or "",
            "selected_city": city or "",
            "cities": cities,
            "zones": zone_options,
            "submitted": submitted,
        }
    )

@app.get("/offers/new", response_class=HTMLResponse)
def offer_form(request: Request):
    return templates.TemplateResponse(
        "offer_form.html",
        {
            "request": request,
            "categories": SERVICE_CATEGORIES,
        }
    )

@app.post("/offers", response_class=HTMLResponse)
def create_offer(
    request: Request,
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form("altro"),
    city: str = Form("Fiumicino"),
    zone: str = Form(""),
    contact_name: str = Form(...),
    contact_method: str = Form(...),
    available_from: str | None = Form(None),
    available_to: str | None = Form(None),
    rate: str | None = Form(None),
    db: Session = Depends(get_db)
):
    offer = ServiceOffer(
        title=title.strip(),
        description=description.strip(),
        category=category.strip() or "altro",
        city=city.strip() or "Fiumicino",
        zone=zone.strip(),
        contact_name=contact_name.strip(),
        contact_method=contact_method.strip(),
        rate=(rate or "").strip(),
        available_from=_parse_date(available_from),
        available_to=_parse_date(available_to),
        status="pending",
    )
    db.add(offer)
    db.commit()
    db.refresh(offer)
    return templates.TemplateResponse(
        "offer_submitted.html",
        {
            "request": request,
            "offer": _serialize_offer(offer),
        },
        status_code=status.HTTP_201_CREATED,
    )

@app.get("/api/offers")
def api_offers(
    status_filter: str = Query("published"),
    category: str | None = Query(None),
    city: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    q = db.query(ServiceOffer).order_by(ServiceOffer.created_at.desc())
    if status_filter:
        q = q.filter(ServiceOffer.status == status_filter)
    if category:
        q = q.filter(ServiceOffer.category == category)
    if city:
        q = q.filter(ServiceOffer.city.ilike(f"%{city}%"))
    offers = q.limit(limit).all()
    return [_serialize_offer(o) for o in offers]

@app.post("/offers/{offer_id}/status")
def update_offer_status(
    offer_id: int,
    new_status: str = Form(...),
    highlight: str | None = Form(None),
    admin_token: str | None = Header(None, alias="X-Admin-Token"),
    db: Session = Depends(get_db)
):
    env_token = os.getenv("ADMIN_TOKEN", "")
    _check_admin(admin_token, env_token)
    offer = db.query(ServiceOffer).filter(ServiceOffer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offerta non trovata")
    allowed = {"pending", "published", "archived", "rejected"}
    if new_status not in allowed:
        raise HTTPException(status_code=400, detail="Stato non valido")
    offer.status = new_status
    if highlight is not None:
        offer.highlighted = highlight.lower() == "true"
    db.commit()
    return {"status": "ok"}

@app.get("/admin/offers", response_class=HTMLResponse)
def admin_offers(
    request: Request,
    token: str | None = Query(None),
    db: Session = Depends(get_db)
):
    env_token = os.getenv("ADMIN_TOKEN", "")
    requires_token = bool(env_token)
    if requires_token:
        _check_admin(token, env_token)
    else:
        token = ""
    pending_count = db.query(ServiceOffer).filter(ServiceOffer.status == "pending").count()
    offers = db.query(ServiceOffer).order_by(ServiceOffer.created_at.desc()).all()
    return templates.TemplateResponse(
        "admin_offers.html",
        {
            "request": request,
            "requires_token": requires_token,
            "admin_token": token or "",
            "pending_count": pending_count,
            "offers": [_serialize_offer(o) for o in offers],
            "categories": SERVICE_CATEGORIES,
            "offer_statuses": OFFER_STATUSES,
        }
    )


@app.get("/businesses", response_class=HTMLResponse)
def businesses_page(
    request: Request,
    city: str | None = Query(None),
    category: str | None = Query(None),
    db: Session = Depends(get_db)
):
    q = db.query(LocalBusiness).order_by(LocalBusiness.highlighted.desc(), LocalBusiness.created_at.desc())
    if city:
        q = q.filter(LocalBusiness.city.ilike(f"%{city}%"))
    if category and category != "tutte":
        q = q.filter(LocalBusiness.category == category)
    businesses = q.limit(30).all()
    cities = sorted({row[0] for row in db.query(LocalBusiness.city).distinct() if row[0]})
    return templates.TemplateResponse(
        "businesses.html",
        {
            "request": request,
            "businesses": [_serialize_business(b) for b in businesses],
            "cities": cities,
            "selected_city": city or "",
            "selected_category": category or "",
            "categories": BUSINESS_CATEGORIES,
        }
    )



@app.get("/businesses/new", response_class=HTMLResponse)
def business_form(request: Request):
    return templates.TemplateResponse(
        "business_form.html",
        {"request": request, "categories": BUSINESS_CATEGORIES}
    )
@app.post("/businesses")
def create_business(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    category: str = Form("servizi"),
    address: str = Form(""),
    city: str = Form("Fiumicino"),
    contact_name: str = Form(""),
    contact_phone: str = Form(""),
    contact_email: str = Form(""),
    website: str = Form(""),
    social_link: str = Form(""),
    image_url: str = Form(""),
    db: Session = Depends(get_db)
):
    biz = LocalBusiness(
        name=name.strip(),
        description=description.strip(),
        category=category.strip() or "servizi",
        address=address.strip(),
        city=city.strip() or "Fiumicino",
        contact_name=contact_name.strip(),
        contact_phone=contact_phone.strip(),
        contact_email=contact_email.strip(),
        website=website.strip(),
        social_link=social_link.strip(),
        image_url=image_url.strip(),
    )
    db.add(biz)
    db.commit()
    db.refresh(biz)
    if "text/html" in request.headers.get("accept", ""):
        return templates.TemplateResponse(
            "business_submitted.html",
            {"request": request, "business": _serialize_business(biz)},
            status_code=status.HTTP_201_CREATED,
        )
    return {"status": "ok", "id": biz.id}

@app.get("/api/businesses")
def api_businesses(
    category: str | None = Query(None),
    city: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    q = db.query(LocalBusiness).order_by(LocalBusiness.created_at.desc())
    if category:
        q = q.filter(LocalBusiness.category == category)
    if city:
        q = q.filter(LocalBusiness.city.ilike(f"%{city}%"))
    return [_serialize_business(b) for b in q.limit(limit).all()]

@app.get("/admin/businesses", response_class=HTMLResponse)
def admin_businesses(
    request: Request,
    token: str | None = Query(None),
    db: Session = Depends(get_db)
):
    env_token = os.getenv("ADMIN_TOKEN", "")
    requires_token = bool(env_token)
    if requires_token:
        _check_admin(token, env_token)
    else:
        token = ""
    businesses = db.query(LocalBusiness).order_by(LocalBusiness.created_at.desc()).all()
    return templates.TemplateResponse(
        "admin_businesses.html",
        {
            "request": request,
            "requires_token": requires_token,
            "admin_token": token or "",
            "businesses": [_serialize_business(b) for b in businesses],
            "categories": BUSINESS_CATEGORIES,
            "categories_map": dict(BUSINESS_CATEGORIES),
        }
    )

@app.post("/businesses/{biz_id}/update")
def update_business(
    biz_id: int,
    name: str = Form(...),
    description: str = Form(""),
    category: str = Form("servizi"),
    address: str = Form(""),
    city: str = Form("Fiumicino"),
    contact_name: str = Form(""),
    contact_phone: str = Form(""),
    contact_email: str = Form(""),
    website: str = Form(""),
    social_link: str = Form(""),
    image_url: str = Form(""),
    highlighted: str = Form("false"),
    admin_token: str | None = Header(None, alias="X-Admin-Token"),
    db: Session = Depends(get_db)
):
    env_token = os.getenv("ADMIN_TOKEN", "")
    _check_admin(admin_token, env_token)
    biz = db.query(LocalBusiness).filter(LocalBusiness.id == biz_id).first()
    if not biz:
        raise HTTPException(status_code=404, detail="Attività non trovata")
    biz.name = name.strip()
    biz.description = description.strip()
    biz.category = category.strip() or "servizi"
    biz.address = address.strip()
    biz.city = city.strip() or "Fiumicino"
    biz.contact_name = contact_name.strip()
    biz.contact_phone = contact_phone.strip()
    biz.contact_email = contact_email.strip()
    biz.website = website.strip()
    biz.social_link = social_link.strip()
    biz.image_url = image_url.strip()
    biz.highlighted = highlighted.lower() == "true"
    db.commit()
    return {"status": "ok"}

@app.delete("/businesses/{biz_id}")
def delete_business(
    biz_id: int,
    admin_token: str | None = Header(None, alias="X-Admin-Token"),
    db: Session = Depends(get_db)
):
    env_token = os.getenv("ADMIN_TOKEN", "")
    _check_admin(admin_token, env_token)
    biz = db.query(LocalBusiness).filter(LocalBusiness.id == biz_id).first()
    if not biz:
        raise HTTPException(status_code=404, detail="Attività non trovata")
    db.delete(biz)
    db.commit()
    return {"status": "ok"}

@app.post("/offers/{offer_id}/update")
def update_offer(
    offer_id: int,
    title: str = Form(...),
    description: str = Form(""),
    category: str = Form("altro"),
    city: str = Form("Fiumicino"),
    zone: str = Form(""),
    contact_name: str = Form(""),
    contact_method: str = Form(""),
    rate: str = Form(""),
    available_from: str = Form(""),
    available_to: str = Form(""),
    status_value: str = Form("pending"),
    highlighted: str = Form("false"),
    admin_token: str | None = Header(None, alias="X-Admin-Token"),
    db: Session = Depends(get_db)
):
    env_token = os.getenv("ADMIN_TOKEN", "")
    _check_admin(admin_token, env_token)
    offer = db.query(ServiceOffer).filter(ServiceOffer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offerta non trovata")
    allowed = {"pending", "published", "archived", "rejected"}
    if status_value not in allowed:
        raise HTTPException(status_code=400, detail="Stato non valido")
    offer.title = title.strip()
    offer.description = description.strip()
    offer.category = category.strip() or "altro"
    offer.city = city.strip() or "Fiumicino"
    offer.zone = zone.strip()
    offer.contact_name = contact_name.strip()
    offer.contact_method = contact_method.strip()
    offer.rate = rate.strip()
    offer.available_from = _parse_date(available_from)
    offer.available_to = _parse_date(available_to)
    offer.status = status_value
    offer.highlighted = highlighted.lower() == "true"
    db.commit()
    return {"status": "ok"}

@app.delete("/offers/{offer_id}")
def delete_offer(
    offer_id: int,
    admin_token: str | None = Header(None, alias="X-Admin-Token"),
    db: Session = Depends(get_db)
):
    env_token = os.getenv("ADMIN_TOKEN", "")
    _check_admin(admin_token, env_token)
    offer = db.query(ServiceOffer).filter(ServiceOffer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offerta non trovata")
    db.delete(offer)
    db.commit()
    return {"status": "ok"}

# Endpoint per richieste pubblicità
@app.get("/ad-request", response_class=HTMLResponse)
def ad_request_form(request: Request):
    return templates.TemplateResponse(
        "ad_request_form.html",
        {"request": request}
    )

@app.post("/ad-requests", response_class=HTMLResponse)
def create_ad_request(
    request: Request,
    business_name: str = Form(...),
    contact_person: str = Form(...),
    email: str = Form(...),
    phone: str = Form(""),
    ad_type: str = Form(...),
    message: str = Form(""),
    db: Session = Depends(get_db)
):
    ad_request = AdRequest(
        business_name=business_name.strip(),
        contact_person=contact_person.strip(),
        email=email.strip(),
        phone=phone.strip(),
        ad_type=ad_type.strip(),
        message=message.strip(),
        status="pending"
    )
    db.add(ad_request)
    db.commit()
    db.refresh(ad_request)

    return templates.TemplateResponse(
        "ad_request_submitted.html",
        {
            "request": request,
            "ad_request": {
                "id": ad_request.id,
                "business_name": ad_request.business_name,
                "contact_person": ad_request.contact_person,
                "email": ad_request.email,
                "ad_type": ad_request.ad_type,
                "created_at": ad_request.created_at.strftime("%d/%m/%Y %H:%M")
            }
        },
        status_code=status.HTTP_201_CREATED,
    )

@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(
    request: Request,
    token: str | None = Query(None),
    db: Session = Depends(get_db)
):
    env_token = os.getenv("ADMIN_TOKEN", "")
    requires_token = bool(env_token)
    if requires_token:
        _check_admin(token, env_token)
    else:
        token = ""

    # Statistiche per la dashboard
    pending_ads_count = db.query(AdRequest).filter(AdRequest.status == "pending").count()
    active_ads_count = db.query(Ad).filter(Ad.active == True).count()
    pending_offers_count = db.query(ServiceOffer).filter(ServiceOffer.status == "pending").count()
    published_offers_count = db.query(ServiceOffer).filter(ServiceOffer.status == "published").count()
    businesses_count = db.query(LocalBusiness).count()
    highlighted_businesses_count = db.query(LocalBusiness).filter(LocalBusiness.highlighted == True).count()
    total_items_count = db.query(Item).count()
    total_offers_count = db.query(ServiceOffer).count()

    return templates.TemplateResponse(
        "admin_dashboard.html",
        {
            "request": request,
            "requires_token": requires_token,
            "admin_token": token or "",
            "pending_ads_count": pending_ads_count,
            "active_ads_count": active_ads_count,
            "pending_offers_count": pending_offers_count,
            "published_offers_count": published_offers_count,
            "businesses_count": businesses_count,
            "highlighted_businesses_count": highlighted_businesses_count,
            "total_items_count": total_items_count,
            "total_offers_count": total_offers_count,
        }
    )

@app.get("/admin/ad-requests", response_class=HTMLResponse)
def admin_ad_requests(
    request: Request,
    token: str | None = Query(None),
    db: Session = Depends(get_db)
):
    env_token = os.getenv("ADMIN_TOKEN", "")
    requires_token = bool(env_token)
    if requires_token:
        _check_admin(token, env_token)
    else:
        token = ""

    pending_count = db.query(AdRequest).filter(AdRequest.status == "pending").count()
    ad_requests = db.query(AdRequest).order_by(AdRequest.created_at.desc()).all()

    ad_type_labels = {
        "feed": "Sponsor nel Feed",
        "sidebar": "Banner Laterale",
        "both": "Pacchetto Completo"
    }

    status_labels = {
        "pending": "In attesa",
        "contacted": "Contattato",
        "approved": "Approvato",
        "rejected": "Rifiutato"
    }

    return templates.TemplateResponse(
        "admin_ad_requests.html",
        {
            "request": request,
            "requires_token": requires_token,
            "admin_token": token or "",
            "pending_count": pending_count,
            "ad_requests": [{
                "id": req.id,
                "business_name": req.business_name,
                "contact_person": req.contact_person,
                "email": req.email,
                "phone": req.phone,
                "ad_type": req.ad_type,
                "ad_type_label": ad_type_labels.get(req.ad_type, req.ad_type),
                "message": req.message,
                "status": req.status,
                "status_label": status_labels.get(req.status, req.status),
                "created_at": req.created_at.strftime("%d/%m/%Y %H:%M")
            } for req in ad_requests],
            "status_options": ["pending", "contacted", "approved", "rejected"],
            "status_labels": status_labels
        }
    )

@app.post("/ad-requests/{request_id}/status")
def update_ad_request_status(
    request_id: int,
    new_status: str = Form(...),
    admin_token: str | None = Header(None, alias="X-Admin-Token"),
    db: Session = Depends(get_db)
):
    env_token = os.getenv("ADMIN_TOKEN", "")
    _check_admin(admin_token, env_token)
    ad_request = db.query(AdRequest).filter(AdRequest.id == request_id).first()
    if not ad_request:
        raise HTTPException(status_code=404, detail="Richiesta non trovata")
    allowed = {"pending", "contacted", "approved", "rejected"}
    if new_status not in allowed:
        raise HTTPException(status_code=400, detail="Stato non valido")
    ad_request.status = new_status
    db.commit()
    return {"status": "ok"}

@app.delete("/ad-requests/{request_id}")
def delete_ad_request(
    request_id: int,
    admin_token: str | None = Header(None, alias="X-Admin-Token"),
    db: Session = Depends(get_db)
):
    env_token = os.getenv("ADMIN_TOKEN", "")
    _check_admin(admin_token, env_token)
    ad_request = db.query(AdRequest).filter(AdRequest.id == request_id).first()
    if not ad_request:
        raise HTTPException(status_code=404, detail="Richiesta non trovata")
    db.delete(ad_request)
    db.commit()
    return {"status": "ok"}

# Pagine legali e informative
@app.get("/privacy-policy", response_class=HTMLResponse)
def privacy_policy(request: Request):
    return templates.TemplateResponse("privacy_policy.html", {"request": request})

@app.get("/terms-conditions", response_class=HTMLResponse)
def terms_conditions(request: Request):
    return templates.TemplateResponse("terms_conditions.html", {"request": request})

@app.get("/disclaimer", response_class=HTMLResponse)
def disclaimer(request: Request):
    return templates.TemplateResponse("disclaimer.html", {"request": request})

@app.get("/about-us", response_class=HTMLResponse)
def about_us(request: Request):
    return templates.TemplateResponse("about_us.html", {"request": request})
