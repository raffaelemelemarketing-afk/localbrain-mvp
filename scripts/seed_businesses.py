from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db import DATABASE_URL
from app.models import LocalBusiness, Base

sample_data = [
    {
        "name": "Coworking Aeroporto",
        "description": "Spazi flessibili con meeting room e postazioni dedicate a due passi dal Leonardo da Vinci.",
        "category": "servizi",
        "address": "Via delle Scienze 12",
        "city": "Fiumicino",
        "contact_name": "Sara",
        "contact_phone": "06 0000000",
        "contact_email": "info@coworkingaeroporto.it",
        "website": "https://coworkingaeroporto.it",
        "social_link": "https://instagram.com/coworkingaeroporto",
        "image_url": "https://images.unsplash.com/photo-1521737604893-d14cc237f11d?auto=format&fit=crop&w=800&q=60",
        "highlighted": True,
    },
    {
        "name": "Studio Dentistico MareBlu",
        "description": "Check-up odontoiatrici e igiene dentale per tutta la famiglia. Convenzioni aziendali.",
        "category": "wellness",
        "address": "Via delle Pleiadi 45",
        "city": "Fiumicino",
        "contact_name": "Dr. Orlando",
        "contact_phone": "06 1111111",
        "contact_email": "segreteria@mareblu.dent",
        "website": "https://marebludentista.it",
        "social_link": "",
        "image_url": "https://images.unsplash.com/photo-1588776814546-1ffcf47267a1?auto=format&fit=crop&w=800&q=60",
        "highlighted": True,
    },
    {
        "name": "Pasticceria La Palma",
        "description": "Cornetti artigianali, catering per eventi e torte personalizzate. Aperta dalle 6 alle 22.",
        "category": "ristorazione",
        "address": "Viale delle Meduse 20",
        "city": "Fiumicino",
        "contact_name": "Federica",
        "contact_phone": "06 2222222",
        "contact_email": "ordini@lapalma.it",
        "website": "https://pasticcerialapalma.it",
        "social_link": "https://facebook.com/pasticcerialapalma",
        "image_url": "https://images.unsplash.com/photo-1589308078055-691f5f91d29c?auto=format&fit=crop&w=800&q=60",
        "highlighted": False,
    },
    {
        "name": "Farmacia Parco Leonardo",
        "description": "Servizi di telemedicina, autoanalisi e consegna farmaci a domicilio.",
        "category": "servizi",
        "address": "Via Portuense 201",
        "city": "Fiumicino",
        "contact_name": "Elena",
        "contact_phone": "06 3333333",
        "contact_email": "info@farmaciap-leonardo.it",
        "website": "",
        "social_link": "",
        "image_url": "https://images.unsplash.com/photo-1580281657521-6dfc0d4e0c05?auto=format&fit=crop&w=800&q=60",
        "highlighted": False,
    },
    {
        "name": "Lido Sunrise",
        "description": "Stabilimento balneare con ristorante e servizi pet-friendly.",
        "category": "turismo",
        "address": "Lungomare della Salute 90",
        "city": "Fiumicino",
        "contact_name": "Marco",
        "contact_phone": "06 4444444",
        "contact_email": "prenotazioni@lidosunrise.it",
        "website": "https://lidosunrise.it",
        "social_link": "https://instagram.com/lidosunrise",
        "image_url": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=800&q=60",
        "highlighted": True,
    },
]

def main():
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        for data in sample_data:
            exists = session.query(LocalBusiness).filter(LocalBusiness.name == data["name"]).first()
            if exists:
                continue
            biz = LocalBusiness(**data)
            session.add(biz)
        session.commit()
        print("Seed completato")
    finally:
        session.close()

if __name__ == "__main__":
    main()
