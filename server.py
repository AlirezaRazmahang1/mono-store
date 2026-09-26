from fastapi import FastAPI, APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict
import uuid
from datetime import datetime, timezone, timedelta
import httpx
import stripe

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(mongo_url)
db_name = os.environ.get('DB_NAME', 'mono_store')
db = client[db_name]

# Stripe configuration
stripe.api_key = os.environ.get('STRIPE_API_KEY', 'sk_test_emergent')

# Create the main app
app = FastAPI()

# CORS middleware (Must be added before routers)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create router with /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== MODELS ====================

class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    user_id: str
    email: str
    name: str
    picture: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class CartItem(BaseModel):
    product_id: str
    quantity: int = 1
    size: str = "M"

class CheckoutRequest(BaseModel):
    session_id: Optional[str] = None
    address_id: Optional[str] = None

# ==================== PRODUCTS (Static Data) ====================

PRODUCTS = {
    "hoodie-1": {
        "id": "hoodie-1",
        "name": "Venom Oversized Hoodie",
        "type": "Hoodie",
        "price": 450.00,
        "description": "Premium heavyweight oversized hoodie with hidden kangaroo pocket. Crafted from 100% organic cotton with a serpentine-inspired silhouette.",
        "sizes": ["XS", "S", "M", "L", "XL", "XXL"],
        "url": "https://images.unsplash.com/photo-1647768617268-06697e8a91d4?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxOTJ8MHwxfHNlYXJjaHwxfHxibGFjayUyMGhvb2RpZSUyMGZhc2hpb24lMjBtb2RlbCUyMGRhcmt8ZW58MHx8fHwxNzc0NTU4OTQ2fDA&ixlib=rb-4.1.0&q=85"
    },
    "hoodie-2": {
        "id": "hoodie-2",
        "name": "Coil Heavyweight Hoodie",
        "type": "Hoodie",
        "price": 480.00,
        "description": "Double-layered heavyweight construction with matte black hardware. Features extended sleeves and dropped shoulders.",
        "sizes": ["XS", "S", "M", "L", "XL", "XXL"],
        "url": "https://images.pexels.com/photos/3894527/pexels-photo-3894527.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"
    },
    "pants-1": {
        "id": "pants-1",
        "name": "Mamba Leather Trousers",
        "type": "Pants",
        "price": 850.00,
        "description": "Full-grain leather trousers with scaled texture detailing. Tailored fit with concealed zip closure.",
        "sizes": ["XS", "S", "M", "L", "XL"],
        "url": "https://images.unsplash.com/photo-1762522926410-9bf43dc9c9e5?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxODd8MHwxfHNlYXJjaHwyfHxibGFjayUyMHBhbnRzJTIwZmFzaGlvbiUyMGRhcmt8ZW58MHx8fHwxNzc0NTU4OTMyfDA&ixlib=rb-4.1.0&q=85"
    },
    "pants-2": {
        "id": "pants-2",
        "name": "Shed Cargo Pants",
        "type": "Pants",
        "price": 620.00,
        "description": "Technical cargo pants with modular pocket system. Water-resistant fabric with articulated knees.",
        "sizes": ["XS", "S", "M", "L", "XL", "XXL"],
        "url": "https://images.pexels.com/photos/5427206/pexels-photo-5427206.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"
    },
    "tshirt-1": {
        "id": "tshirt-1",
        "name": "Fangs Boxy Tee",
        "type": "T-shirt",
        "price": 220.00,
        "description": "Oversized boxy silhouette tee in heavyweight cotton. Features subtle embossed logo at back neck.",
        "sizes": ["XS", "S", "M", "L", "XL", "XXL"],
        "url": "https://images.unsplash.com/photo-1762914395034-67c2f8c73c59?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxODd8MHwxfHNlYXJjaHwyfHxibGFjayUyMHN0cmVldHdlYXIlMjBtb2RlbCUyMGRhcmt8ZW58MHx8fHwxNzc0NTU4OTMyfDA&ixlib=rb-4.1.0&q=85"
    }
}

# ==================== AUTH HELPERS ====================

async def get_current_user(request: Request) -> Optional[User]:
    session_token = request.cookies.get("session_token")
    if not session_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            session_token = auth_header.split(" ")[1]
    
    if not session_token:
        return None
    
    session_doc = await db.user_sessions.find_one({"session_token": session_token}, {"_id": 0})
    if not session_doc:
        return None
    
    user_doc = await db.users.find_one({"user_id": session_doc["user_id"]}, {"_id": 0})
    if not user_doc:
        return None
    
    return User(**user_doc)

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
    cart = await db.carts.find_one(query, {"_id": 0})
    
    if not cart:
        cart = {
            "cart_id": f"cart_{uuid.uuid4().hex[:12]}",
            "user_id": user_id,
            "session_id": session_id if not user_id else None,
            "items": [],
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        await db.carts.insert_one(cart)
    return cart

class AddToCartRequest(BaseModel):
    product_id: str
    quantity: int = 1
    size: str = "M"
    session_id: Optional[str] = None

@api_router.post("/cart/add")
async def add_to_cart(request: Request, item: AddToCartRequest):
    if item.product_id not in PRODUCTS:
        raise HTTPException(status_code=404, detail="Product not found")
    
    user = await get_current_user(request)
    user_id = user.user_id if user else None
    session_id = item.session_id or str(uuid.uuid4())
    
    cart = await get_or_create_cart(user_id, session_id)
    items = cart.get("items", [])
    
    found = False
    for i, cart_item in enumerate(items):
        if cart_item["product_id"] == item.product_id and cart_item["size"] == item.size:
            items[i]["quantity"] += item.quantity
            found = True
            break
    
    if not found:
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

class GetCartRequest(BaseModel):
    session_id: Optional[str] = None

@api_router.post("/cart")
async def get_cart(request: Request, body: GetCartRequest):
    user = await get_current_user(request)
    user_id = user.user_id if user else None
    
    query = {"user_id": user_id} if user_id else {"session_id": body.session_id}
    cart = await db.carts.find_one(query, {"_id": 0})
    
    if not cart:
        return {"items": [], "total": 0}
    
    enriched_items = []
    total = 0
    for item in cart.get("items", []):
        product = PRODUCTS.get(item["product_id"])
        if product:
            enriched_item = {
                **item,
                "name": product["name"],
                "price": product["price"],
                "url": product["url"],
                "type": product["type"]
            }
            enriched_items.append(enriched_item)
            total += product["price"] * item["quantity"]
    
    return {"items": enriched_items, "total": total, "cart_id": cart.get("cart_id")}

# ==================== CHECKOUT ROUTES ====================

@api_router.post("/checkout/create-session")
async def create_checkout_session(request: Request, body: CheckoutRequest):
    user = await get_current_user(request)
    user_id = user.user_id if user else None
    
    query = {"user_id": user_id} if user_id else {"session_id": body.session_id}
    cart = await db.carts.find_one(query, {"_id": 0})
    
    if not cart or not cart.get("items"):
        raise HTTPException(status_code=400, detail="Cart is empty")
    
    total = 0.0
    line_items = []
    for item in cart.get("items", []):
        product = PRODUCTS.get(item["product_id"])
        if product:
            total += product["price"] * item["quantity"]
            line_items.append({
                'price_data': {
                    'currency': 'usd',
                    'product_data': {'name': product["name"]},
                    'unit_amount': int(product["price"] * 100),
                },
                'quantity': item["quantity"],
            })
            
    origin = request.headers.get("origin", "https://monowearofficial.netlify.app")
    success_url = f"{origin}/checkout/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/cart"
    
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            success_url=success_url,
            cancel_url=cancel_url,
        )
        return {"url": checkout_session.url, "session_id": checkout_session.id}
    except Exception as e:
        logger.error(f"Stripe error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== BASIC ROUTES ====================

@api_router.get("/")
async def root():
    return {"message": "MONO API v1.0 running"}

app.include_router(api_router)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
