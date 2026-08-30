# Farm2Market

Full-stack reference implementation of the flow you sketched:

```
Farmer/FPO -> Register/Login -> Add Produce -> List on Platform
   -> Buyer Marketplace (bulk / individual)
   -> Place Order -> Save Order in DB -> Smart Order Engine
        (match inventory, check qty/location/time, calc demand)
   -> Bulk: direct order processing
      Individual: find nearby orders (same area + slot) -> batch or
                  offer direct delivery for an extra cost
   -> Calculate Delivery Requirement -> Find Logistics Partners
      -> Smart Logistics Selection (cost, capacity, distance, availability)
      -> Select best/cheapest option -> Optimize pickup + delivery route
   -> Farmer/FPO pickup -> Optimized delivery route -> Product delivered
   -> Delivery confirmation (OTP) -> Payment settlement
      -> Farmer/FPO receives produce value
      -> Logistics partner payment
      -> Platform revenue
```

Backend: **FastAPI** + **SQLAlchemy** + **PostgreSQL**, JWT auth.
Frontend: plain **HTML/CSS/JS** calling the API directly (no build step).

Every "Add Produce Details" and buyer/order/payment action writes straight
into PostgreSQL through SQLAlchemy models — nothing is kept only in memory.

## Project layout

```
farm2market/
  backend/
    app/
      main.py            FastAPI app + router wiring
      config.py           settings (reads .env)
      database.py         SQLAlchemy engine/session
      models.py           ORM models (User, Produce, Order, DeliveryBatch,
                           LogisticsPartner, Delivery, Payment, ...)
      schemas.py           Pydantic request/response models
      routers/
        auth.py            register / login / me
        produce.py         add produce, browse marketplace
        orders.py           place order, my orders, request direct delivery
        logistics.py         partners, delivery status, OTP confirmation
        payments.py          settlement record, platform revenue
      services/
        order_engine.py      Smart Order Engine (match/check/calc, bulk vs individual)
        batch_engine.py       batching by area + time slot, direct-delivery override
        logistics_engine.py    partner selection + route optimization
        payment_engine.py       OTP confirmation -> payment settlement
      utils/
        security.py           password hashing + JWT
        otp.py                  OTP generation
        geo.py                   distance estimate + area key for batching
    requirements.txt
    Dockerfile
    seed.py               seeds a few demo logistics partners
    .env.example
  frontend/
    index.html            login / register
    dashboard.html          role-based app shell
    css/style.css
    js/api.js, auth.js, dashboard.js
  docker-compose.yml       Postgres + backend, one command
```

## Run it

### Option A — Docker (fastest)

```bash
docker compose up --build
```

This starts PostgreSQL and the API on `http://localhost:8000`. Then seed a
few logistics partners so orders have something to be matched against:

```bash
docker compose exec backend python seed.py
```

Open `frontend/index.html` directly in your browser (or serve the folder
with any static server, e.g. `python -m http.server` from inside
`frontend/`).

### Option B — Run locally without Docker

1. Install PostgreSQL locally and create a database + user matching
   `backend/.env.example`, or just edit `DATABASE_URL` to match your setup.
2. ```bash
   cd backend
   cp .env.example .env      # then edit values as needed
   python -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   python seed.py             # creates tables + demo logistics partners
   uvicorn app.main:app --reload
   ```
3. Open `frontend/index.html` in a browser. The frontend expects the API
   at `http://localhost:8000` (see `frontend/js/api.js` — change
   `API_BASE` if you deploy the backend elsewhere).

API docs (Swagger) are auto-generated at `http://localhost:8000/docs`.

## How the demo maps to your flowchart

- **Register/Login, Add Produce Details, List Produce on Platform** —
  `routers/auth.py`, `routers/produce.py`. Farmers fill in product,
  quantity, quality, available date, and pickup location; it's saved to
  the `produce` table immediately.
- **Buyer Marketplace (bulk vs individual)** — a buyer's `buyer_type` is
  fixed at registration; the marketplace UI is the same, `order_type` on
  each order is derived from it.
- **Smart Order Engine** — `services/order_engine.py` matches produce,
  checks stock, deducts inventory, computes the order total, then
  branches bulk vs individual.
- **Find Nearby Orders / batching** — `services/batch_engine.py` groups
  individual orders sharing the same (normalized) delivery area and time
  slot into a `DeliveryBatch`; once weight or order-count thresholds are
  hit, logistics gets assigned. Buyers waiting in an unfilled batch can
  call "request direct delivery" to opt out for an extra cost.
- **Calculate Delivery Requirement / Smart Logistics Selection /
  Optimize Route** — `services/logistics_engine.py` picks the
  cheapest available partner with enough capacity (and cold-chain support
  when the produce needs it), then builds a stop sequence for the batch.
- **Delivery Confirmation (OTP) / Payment Settlement / Platform
  Revenue** — `services/payment_engine.py` verifies the OTP, marks the
  delivery complete, and splits the order total between the farmer, the
  logistics partner, and the platform fee. `GET /platform/revenue`
  (admin only) totals it all up.

## Notes / next steps for production

- `estimate_distance_km` uses real lat/long when both points have them,
  otherwise derives a stable placeholder distance from location text —
  swap in a real geocoding/routing API (Google Maps, Mapbox, OSRM) for
  production-accurate distances and route optimization.
- Add an admin-creation path (currently create one by registering a user
  then updating their `role` to `admin` directly in the database) if you
  need the `/platform/revenue` dashboard.
- Payments here are bookkeeping records only — plug in a real payment
  gateway (Razorpay/Stripe/UPI) for actual money movement.
- Tighten CORS (`app/main.py`) to your real frontend origin before
  deploying.
