from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import secrets
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict
import uuid
from datetime import datetime, timezone, timedelta
import stripe
from passlib.context import CryptContext

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# ==================== CONFIG ====================

mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(mongo_url)
db_name = os.environ.get('DB_NAME', 'mono_store')
db = client[db_name]

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

stripe_key = os.environ.get('STRIPE_API_KEY')
if not stripe_key:
    logger.warning("STRIPE_API_KEY is not set. Checkout will fail until it is configured.")
stripe.api_key = stripe_key

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:3000')
COOKIE_SECURE = os.environ.get('COOKIE_SECURE', 'true').lower() == 'true'
SESSION_COOKIE = "session_token"
SESSION_TTL_DAYS = 30

app = FastAPI(title="MONO API")

# CORS: no wildcard — credentialed requests require an explicit origin list.
allowed_origins = [o.strip() for o in os.environ.get('CORS_ORIGINS', FRONTEND_URL).split(',') if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_router = APIRouter(prefix="/api")

# ==================== MODELS ====================

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=100)
    session_id: Optional[str] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    session_id: Optional[str] = None

class CheckoutRequest(BaseModel):
    session_id: Optional[str] = None

class AddToCartRequest(BaseModel):
    product_id: str
    quantity: int = Field(default=1, ge=1, le=20)
    size: str = "M"
    session_id: Optional[str] = None

class GetCartRequest(BaseModel):
    session_id: Optional[str] = None

class UpdateCartRequest(BaseModel):
    product_id: str
    size: str
    quantity: int = Field(ge=0, le=20)
    session_id: Optional[str] = None

class RemoveCartRequest(BaseModel):
    product_id: str
    size: str
    session_id: Optional[str] = None

class WishlistAddRequest(BaseModel):
    product_id: str

class AddressRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    street: str = Field(min_length=1, max_length=200)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(min_length=1, max_length=100)
    zip_code: str = Field(min_length=1, max_length=20)
    country: str = Field(min_length=1, max_length=100)
    is_default: bool = False

class NewsletterRequest(BaseModel):
    email: EmailStr

# ==================== PRODUCTS (Static Data) ====================

PRODUCTS = {
    "hoodie-1": {
        "id": "hoodie-1",
        "name": "Venom Oversized Hoodie",
        "type": "Hoodie",
        "category": "men",
        "price": 450.00,
        "description": "Premium heavyweight oversized hoodie with hidden kangaroo pocket. Crafted from 100% organic cotton with a serpentine-inspired silhouette.",
        "sizes": ["XS", "S", "M", "L", "XL", "XXL"],
        "url": "https://images.unsplash.com/photo-1647768617268-06697e8a91d4?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxOTJ8MHwxfHNlYXJjaHwxfHxibGFjayUyMGhvb2RpZSUyMGZhc2hpb24lMjBtb2RlbCUyMGRhcmt8ZW58MHx8fHwxNzc0NTU4OTQ2fDA&ixlib=rb-4.1.0&q=85"
    },
    "hoodie-2": {
        "id": "hoodie-2",
        "name": "Coil Heavyweight Hoodie",
        "type": "Hoodie",
        "category": "women",
        "price": 480.00,
        "description": "Double-layered heavyweight construction with matte black hardware. Features extended sleeves and dropped shoulders.",
        "sizes": ["XS", "S", "M", "L", "XL", "XXL"],
        "url": "https://images.pexels.com/photos/3894527/pexels-photo-3894527.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"
    },
    "pants-1": {
        "id": "pants-1",
        "name": "Mamba Leather Trousers",
        "type": "Pants",
        "category": "men",
        "price": 850.00,
        "description": "Full-grain leather trousers with scaled texture detailing. Tailored fit with concealed zip closure.",
        "sizes": ["XS", "S", "M", "L", "XL"],
        "url": "https://images.unsplash.com/photo-1762522926410-9bf43dc9c9e5?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxODd8MHwxfHNlYXJjaHwyfHxibGFjayUyMHBhbnRzJTIwZmFzaGlvbiUyMGRhcmt8ZW58MHx8fHwxNzc0NTU4OTMyfDA&ixlib=rb-4.1.0&q=85"
    },
    "pants-2": {
        "id": "pants-2",
        "name": "Shed Cargo Pants",
        "type": "Pants",
        "category": "women",
        "price": 620.00,
        "description": "Technical cargo pants with modular pocket system. Water-resistant fabric with articulated knees.",
        "sizes": ["XS", "S", "M", "L", "XL", "XXL"],
        "url": "https://images.pexels.com/photos/5427206/pexels-photo-5427206.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"
    },
    "tshirt-1": {
        "id": "tshirt-1",
        "name": "Fangs Boxy Tee",
        "type": "T-shirt",
        "category": "men",
        "price": 220.00,
        "description": "Oversized boxy silhouette tee in heavyweight cotton. Features subtle embossed logo at back neck.",
        "sizes": ["XS", "S", "M", "L", "XL", "XXL"],
        "url": "https://images.unsplash.com/photo-1762914395034-67c2f8c73c59?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxODd8MHwxfHNlYXJjaHwyfHxibGFjayUyMHN0cmVldHdlYXIlMjBtb2RlbCUyMGRhcmt8ZW58MHx8fHwxNzc0NTU4OTMyfDA&ixlib=rb-4.1.0&q=85"
    }
}

# ==================== AUTH HELPERS ====================

async def create_session(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    await db.user_sessions.insert_one({
        "session_token": token,
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS)
    })
    return token

def set_session_cookie(response: Response, token: str):
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=SESSION_TTL_DAYS * 24 * 3600,
        path="/"
    )

def clear_session_cookie(response: Response):
    response.delete_cookie(SESSION_COOKIE, path="/")

def public_user(user_doc: Dict) -> Dict:
    return {
        "user_id": user_doc["user_id"],
        "email": user_doc["email"],
        "name": user_doc["name"],
        "created_at": user_doc["created_at"]
    }

async def get_current_user(request: Request) -> Optional[Dict]:
    session_token = request.cookies.get(SESSION_COOKIE)
    if not session_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            session_token = auth_header.split(" ")[1]

    if not session_token:
        return None

    session_doc = await db.user_sessions.find_one({"session_token": session_token})
    if not session_doc:
        return None

    expires_at = session_doc.get("expires_at")
    if expires_at and expires_at < datetime.now(timezone.utc):
        await db.user_sessions.delete_one({"session_token": session_token})
        return None

    user_doc = await db.users.find_one({"user_id": session_doc["user_id"]})
    if not user_doc:
        return None

    return public_user(user_doc)

async def require_user(request: Request) -> Dict:
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

async def merge_guest_cart(user_id: str, session_id: Optional[str]):
    """Fold a guest cart (identified by session_id) into the newly logged-in user's cart."""
    if not session_id:
        return

    guest_cart = await db.carts.find_one({"session_id": session_id, "user_id": None})
    if not guest_cart or not guest_cart.get("items"):
        return

    user_cart = await db.carts.find_one({"user_id": user_id})
    now = datetime.now(timezone.utc).isoformat()

    if not user_cart:
        await db.carts.update_one(
            {"user_id": user_id},
            {"$set": {
                "cart_id": guest_cart.get("cart_id", f"cart_{uuid.uuid4().hex[:12]}"),
                "user_id": user_id,
                "session_id": None,
                "items": guest_cart["items"],
                "updated_at": now
            }},
            upsert=True
        )
    else:
        items = user_cart.get("items", [])
        for g_item in guest_cart.get("items", []):
            for item in items:
                if item["product_id"] == g_item["product_id"] and item["size"] == g_item["size"]:
                    item["quantity"] = min(item["quantity"] + g_item["quantity"], 20)
                    break
            else:
                items.append(g_item)
        await db.carts.update_one({"user_id": user_id}, {"$set": {"items": items, "updated_at": now}})

    await db.carts.delete_one({"session_id": session_id, "user_id": None})

# ==================== AUTH ROUTES ====================

@api_router.post("/auth/register")
async def register(body: RegisterRequest, response: Response):
    email = body.email.lower()
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists")

    user_id = f"user_{uuid.uuid4().hex[:12]}"
    user_doc = {
        "user_id": user_id,
        "email": email,
        "name": body.name.strip(),
        "password_hash": pwd_context.hash(body.password),
        "created_at": datetime.now(timezone.utc)
    }
    await db.users.insert_one(user_doc)

    token = await create_session(user_id)
    set_session_cookie(response, token)
    await merge_guest_cart(user_id, body.session_id)

    return public_user(user_doc)

@api_router.post("/auth/login")
async def login(body: LoginRequest, response: Response):
    email = body.email.lower()
    user_doc = await db.users.find_one({"email": email})
    if not user_doc or not pwd_context.verify(body.password, user_doc["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = await create_session(user_doc["user_id"])
    set_session_cookie(response, token)
    await merge_guest_cart(user_doc["user_id"], body.session_id)

    return public_user(user_doc)

@api_router.post("/auth/logout")
async def logout(request: Request, response: Response):
    session_token = request.cookies.get(SESSION_COOKIE)
    if session_token:
        await db.user_sessions.delete_one({"session_token": session_token})
    clear_session_cookie(response)
    return {"message": "Logged out"}

@api_router.get("/auth/me")
async def me(user: Dict = Depends(require_user)):
    return user

# ==================== PRODUCTS ROUTES ====================

@api_router.get("/products")
async def get_products():
    return list(PRODUCTS.values())

@api_router.get("/products/{product_id}")
async def get_product(product_id: str):
    if product_id not in PRODUCTS:
        raise HTTPException(status_code=404, detail="Product not found")
    return PRODUCTS[product_id]

# ==================== CART ROUTES ====================

async def get_or_create_cart(user_id: Optional[str], session_id: str) -> Dict:
    query = {"user_id": user_id} if user_id else {"session_id": session_id}
    cart = await db.carts.find_one(query)

    if not cart:
        cart = {
            "cart_id": f"cart_{uuid.uuid4().hex[:12]}",
            "user_id": user_id,
            "session_id": session_id if not user_id else None,
            "items": [],
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        await db.carts.insert_one(dict(cart))
    return cart

@api_router.post("/cart/add")
async def add_to_cart(request: Request, item: AddToCartRequest):
    product = PRODUCTS.get(item.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if item.size not in product["sizes"]:
        raise HTTPException(status_code=400, detail="Size not available for this product")

    user = await get_current_user(request)
    user_id = user["user_id"] if user else None
    session_id = item.session_id or str(uuid.uuid4())

    cart = await get_or_create_cart(user_id, session_id)
    items = cart.get("items", [])

    for i, cart_item in enumerate(items):
        if cart_item["product_id"] == item.product_id and cart_item["size"] == item.size:
            items[i]["quantity"] = min(items[i]["quantity"] + item.quantity, 20)
            break
    else:
        items.append({
            "product_id": item.product_id,
            "quantity": item.quantity,
            "size": item.size
        })

    query = {"user_id": user_id} if user_id else {"session_id": session_id}
    await db.carts.update_one(
        query,
        {"$set": {"items": items, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True
    )
    return {"message": "Added to cart", "cart_session_id": session_id}

@api_router.post("/cart")
async def get_cart(request: Request, body: GetCartRequest):
    user = await get_current_user(request)
    user_id = user["user_id"] if user else None

    if not user_id and not body.session_id:
        return {"items": [], "total": 0}

    query = {"user_id": user_id} if user_id else {"session_id": body.session_id}
    cart = await db.carts.find_one(query)

    if not cart:
        return {"items": [], "total": 0}

    enriched_items = []
    total = 0
    for item in cart.get("items", []):
        product = PRODUCTS.get(item["product_id"])
        if product:
            enriched_items.append({
                **item,
                "name": product["name"],
                "price": product["price"],
                "url": product["url"],
                "type": product["type"]
            })
            total += product["price"] * item["quantity"]

    return {"items": enriched_items, "total": total, "cart_id": cart.get("cart_id")}

@api_router.put("/cart/update")
async def update_cart_item(request: Request, body: UpdateCartRequest):
    user = await get_current_user(request)
    user_id = user["user_id"] if user else None

    query = {"user_id": user_id} if user_id else {"session_id": body.session_id}
    cart = await db.carts.find_one(query)
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    items = cart.get("items", [])
    if body.quantity <= 0:
        items = [i for i in items if not (i["product_id"] == body.product_id and i["size"] == body.size)]
    else:
        for i in items:
            if i["product_id"] == body.product_id and i["size"] == body.size:
                i["quantity"] = body.quantity
                break
        else:
            raise HTTPException(status_code=404, detail="Item not in cart")

    await db.carts.update_one(query, {"$set": {"items": items, "updated_at": datetime.now(timezone.utc).isoformat()}})
    return {"message": "Cart updated"}

@api_router.post("/cart/remove")
async def remove_cart_item(request: Request, body: RemoveCartRequest):
    user = await get_current_user(request)
    user_id = user["user_id"] if user else None

    query = {"user_id": user_id} if user_id else {"session_id": body.session_id}
    cart = await db.carts.find_one(query)
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    items = [i for i in cart.get("items", []) if not (i["product_id"] == body.product_id and i["size"] == body.size)]
    await db.carts.update_one(query, {"$set": {"items": items, "updated_at": datetime.now(timezone.utc).isoformat()}})
    return {"message": "Item removed"}

# ==================== WISHLIST ROUTES ====================

@api_router.get("/wishlist")
async def get_wishlist(user: Dict = Depends(require_user)):
    docs = await db.wishlists.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(200)
    result = []
    for d in docs:
        product = PRODUCTS.get(d["product_id"])
        if product:
            result.append({"product_id": d["product_id"], "product": product})
    return result

@api_router.post("/wishlist/add")
async def add_to_wishlist(body: WishlistAddRequest, user: Dict = Depends(require_user)):
    if body.product_id not in PRODUCTS:
        raise HTTPException(status_code=404, detail="Product not found")

    existing = await db.wishlists.find_one({"user_id": user["user_id"], "product_id": body.product_id})
    if existing:
        return {"message": "Already in wishlist"}

    await db.wishlists.insert_one({
        "user_id": user["user_id"],
        "product_id": body.product_id,
        "created_at": datetime.now(timezone.utc)
    })
    return {"message": "Added to wishlist"}

@api_router.delete("/wishlist/{product_id}")
async def remove_from_wishlist(product_id: str, user: Dict = Depends(require_user)):
    await db.wishlists.delete_one({"user_id": user["user_id"], "product_id": product_id})
    return {"message": "Removed from wishlist"}

# ==================== ADDRESS ROUTES ====================

@api_router.get("/addresses")
async def list_addresses(user: Dict = Depends(require_user)):
    return await db.addresses.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(50)

@api_router.post("/addresses")
async def add_address(body: AddressRequest, user: Dict = Depends(require_user)):
    address_id = f"addr_{uuid.uuid4().hex[:12]}"
    doc = {"address_id": address_id, "user_id": user["user_id"], **body.model_dump()}

    if body.is_default:
        await db.addresses.update_many({"user_id": user["user_id"]}, {"$set": {"is_default": False}})

    await db.addresses.insert_one(dict(doc))
    doc.pop("_id", None)
    return doc

@api_router.delete("/addresses/{address_id}")
async def delete_address(address_id: str, user: Dict = Depends(require_user)):
    result = await db.addresses.delete_one({"address_id": address_id, "user_id": user["user_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Address not found")
    return {"message": "Address deleted"}

# ==================== CHECKOUT & ORDER ROUTES ====================

@api_router.post("/checkout/create-session")
async def create_checkout_session(request: Request, body: CheckoutRequest, user: Dict = Depends(require_user)):
    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="Payments are not configured")

    cart = await db.carts.find_one({"user_id": user["user_id"]})
    if not cart or not cart.get("items"):
        raise HTTPException(status_code=400, detail="Cart is empty")

    total = 0.0
    line_items = []
    order_items = []
    for item in cart["items"]:
        product = PRODUCTS.get(item["product_id"])
        if not product:
            continue
        total += product["price"] * item["quantity"]
        line_items.append({
            'price_data': {
                'currency': 'usd',
                'product_data': {'name': f'{product["name"]} ({item["size"]})'},
                'unit_amount': int(round(product["price"] * 100)),
            },
            'quantity': item["quantity"],
        })
        order_items.append({
            "product_id": item["product_id"],
            "size": item["size"],
            "quantity": item["quantity"],
            "name": product["name"],
            "price": product["price"],
            "url": product["url"]
        })

    if not line_items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    origin = request.headers.get("origin") or FRONTEND_URL
    success_url = f"{origin}/checkout/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/cart"

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"user_id": user["user_id"]}
        )
    except Exception as e:
        logger.error(f"Stripe error: {e}")
        raise HTTPException(status_code=500, detail="Could not start checkout")

    order_id = f"order_{uuid.uuid4().hex[:12]}"
    await db.orders.insert_one({
        "order_id": order_id,
        "user_id": user["user_id"],
        "stripe_session_id": checkout_session.id,
        "items": order_items,
        "total": round(total, 2),
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    return {"url": checkout_session.url, "session_id": checkout_session.id}

@api_router.get("/checkout/status/{session_id}")
async def checkout_status(session_id: str, user: Dict = Depends(require_user)):
    order = await db.orders.find_one({"stripe_session_id": session_id, "user_id": user["user_id"]}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order["status"] == "confirmed":
        return {"payment_status": "paid", "status": "confirmed", "order_id": order["order_id"]}

    try:
        stripe_session = stripe.checkout.Session.retrieve(session_id)
    except Exception as e:
        logger.error(f"Stripe status check failed: {e}")
        raise HTTPException(status_code=502, detail="Could not verify payment status")

    if stripe_session.payment_status == "paid":
        await db.orders.update_one({"order_id": order["order_id"]}, {"$set": {"status": "confirmed"}})
        await db.carts.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"items": [], "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        return {"payment_status": "paid", "status": "confirmed", "order_id": order["order_id"]}

    if stripe_session.status == "expired":
        await db.orders.update_one({"order_id": order["order_id"]}, {"$set": {"status": "expired"}})
        return {"payment_status": stripe_session.payment_status, "status": "expired"}

    return {"payment_status": stripe_session.payment_status, "status": stripe_session.status}

@api_router.get("/orders")
async def get_orders(user: Dict = Depends(require_user)):
    orders = await db.orders.find(
        {"user_id": user["user_id"], "status": "confirmed"}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return orders

# ==================== NEWSLETTER ====================

@api_router.post("/newsletter/subscribe")
async def subscribe_newsletter(body: NewsletterRequest):
    await db.newsletter.update_one(
        {"email": body.email.lower()},
        {"$setOnInsert": {"email": body.email.lower(), "created_at": datetime.now(timezone.utc)}},
        upsert=True
    )
    return {"message": "Subscribed"}

# ==================== BASIC ROUTES ====================

@api_router.get("/")
async def root():
    return {"message": "MONO API v2.0 running"}

app.include_router(api_router)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
