from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends
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
from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout, 
    CheckoutSessionResponse, 
    CheckoutStatusResponse, 
    CheckoutSessionRequest
)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Stripe configuration
STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY', 'sk_test_emergent')

# Create the main app
app = FastAPI()

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

class UserSession(BaseModel):
    model_config = ConfigDict(extra="ignore")
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    session_token: str
    expires_at: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Address(BaseModel):
    model_config = ConfigDict(extra="ignore")
    address_id: str = Field(default_factory=lambda: f"addr_{uuid.uuid4().hex[:12]}")
    user_id: str
    name: str
    street: str
    city: str
    state: str
    zip_code: str
    country: str = "United States"
    is_default: bool = False

class CartItem(BaseModel):
    product_id: str
    quantity: int = 1
    size: str = "M"

class Cart(BaseModel):
    model_config = ConfigDict(extra="ignore")
    cart_id: str = Field(default_factory=lambda: f"cart_{uuid.uuid4().hex[:12]}")
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    items: List[CartItem] = []
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class WishlistItem(BaseModel):
    product_id: str
    added_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Order(BaseModel):
    model_config = ConfigDict(extra="ignore")
    order_id: str = Field(default_factory=lambda: f"ORD-{uuid.uuid4().hex[:8].upper()}")
    user_id: str
    items: List[Dict]
    total: float
    status: str = "pending"
    shipping_address: Optional[Dict] = None
    payment_session_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PaymentTransaction(BaseModel):
    model_config = ConfigDict(extra="ignore")
    transaction_id: str = Field(default_factory=lambda: f"txn_{uuid.uuid4().hex[:12]}")
    session_id: str
    user_id: Optional[str] = None
    email: Optional[str] = None
    amount: float
    currency: str = "usd"
    status: str = "pending"
    payment_status: str = "initiated"
    metadata: Optional[Dict] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class NewsletterSubscription(BaseModel):
    model_config = ConfigDict(extra="ignore")
    subscription_id: str = Field(default_factory=lambda: f"sub_{uuid.uuid4().hex[:12]}")
    email: str
    subscribed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

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
    """Get current user from session token (cookie or header)"""
    session_token = request.cookies.get("session_token")
    if not session_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            session_token = auth_header.split(" ")[1]
    
    if not session_token:
        return None
    
    session_doc = await db.user_sessions.find_one(
        {"session_token": session_token},
        {"_id": 0}
    )
    
    if not session_doc:
        return None
    
    # Check expiry with timezone awareness
    expires_at = session_doc.get("expires_at")
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        return None
    
    user_doc = await db.users.find_one(
        {"user_id": session_doc["user_id"]},
        {"_id": 0}
    )
    
    if not user_doc:
        return None
    
    return User(**user_doc)

async def require_auth(request: Request) -> User:
    """Require authenticated user"""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

# ==================== AUTH ROUTES ====================

class SessionRequest(BaseModel):
    session_id: str

@api_router.post("/auth/session")
async def exchange_session(request: Request, session_req: SessionRequest, response: Response):
    """Exchange session_id for session_token after Google OAuth"""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
                headers={"X-Session-ID": session_req.session_id}
            )
            
            if resp.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid session")
            
            data = resp.json()
            
            # Check if user exists
            existing_user = await db.users.find_one(
                {"email": data["email"]},
                {"_id": 0}
            )
            
            if existing_user:
                user_id = existing_user["user_id"]
                # Update user info if needed
                await db.users.update_one(
                    {"user_id": user_id},
                    {"$set": {
                        "name": data["name"],
                        "picture": data.get("picture")
                    }}
                )
            else:
                user_id = f"user_{uuid.uuid4().hex[:12]}"
                user_doc = {
                    "user_id": user_id,
                    "email": data["email"],
                    "name": data["name"],
                    "picture": data.get("picture"),
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
                await db.users.insert_one(user_doc)
            
            # Create session
            session_token = data["session_token"]
            session_doc = {
                "session_id": str(uuid.uuid4()),
                "user_id": user_id,
                "session_token": session_token,
                "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.user_sessions.insert_one(session_doc)
            
            # Set cookie
            response.set_cookie(
                key="session_token",
                value=session_token,
                httponly=True,
                secure=True,
                samesite="none",
                path="/",
                max_age=7 * 24 * 60 * 60
            )
            
            user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
            return user
            
    except httpx.HTTPError as e:
        logger.error(f"Auth error: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")

@api_router.get("/auth/me")
async def get_me(request: Request):
    """Get current authenticated user"""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user.model_dump()

@api_router.post("/auth/logout")
async def logout(request: Request, response: Response):
    """Logout current user"""
    session_token = request.cookies.get("session_token")
    if session_token:
        await db.user_sessions.delete_one({"session_token": session_token})
    
    response.delete_cookie(key="session_token", path="/")
    return {"message": "Logged out successfully"}

# ==================== PRODUCTS ROUTES ====================

@api_router.get("/products")
async def get_products():
    """Get all products"""
    return list(PRODUCTS.values())

@api_router.get("/products/{product_id}")
async def get_product(product_id: str):
    """Get single product"""
    if product_id not in PRODUCTS:
        raise HTTPException(status_code=404, detail="Product not found")
    return PRODUCTS[product_id]

# ==================== CART ROUTES ====================

async def get_or_create_cart(user_id: Optional[str], session_id: str) -> Dict:
    """Get or create cart for user/session"""
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
    """Add item to cart"""
    if item.product_id not in PRODUCTS:
        raise HTTPException(status_code=404, detail="Product not found")
    
    user = await get_current_user(request)
    user_id = user.user_id if user else None
    session_id = item.session_id or str(uuid.uuid4())
    
    cart = await get_or_create_cart(user_id, session_id)
    
    # Check if item already exists
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
        {"$set": {"items": items, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {"message": "Added to cart", "cart_session_id": session_id}

class GetCartRequest(BaseModel):
    session_id: Optional[str] = None

@api_router.post("/cart")
async def get_cart(request: Request, body: GetCartRequest):
    """Get cart contents"""
    user = await get_current_user(request)
    user_id = user.user_id if user else None
    
    query = {"user_id": user_id} if user_id else {"session_id": body.session_id}
    cart = await db.carts.find_one(query, {"_id": 0})
    
    if not cart:
        return {"items": [], "total": 0}
    
    # Enrich with product data
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

class UpdateCartItemRequest(BaseModel):
    product_id: str
    size: str
    quantity: int
    session_id: Optional[str] = None

@api_router.put("/cart/update")
async def update_cart_item(request: Request, body: UpdateCartItemRequest):
    """Update cart item quantity"""
    user = await get_current_user(request)
    user_id = user.user_id if user else None
    
    query = {"user_id": user_id} if user_id else {"session_id": body.session_id}
    cart = await db.carts.find_one(query, {"_id": 0})
    
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    
    items = cart.get("items", [])
    if body.quantity <= 0:
        items = [i for i in items if not (i["product_id"] == body.product_id and i["size"] == body.size)]
    else:
        for i, item in enumerate(items):
            if item["product_id"] == body.product_id and item["size"] == body.size:
                items[i]["quantity"] = body.quantity
                break
    
    await db.carts.update_one(
        query,
        {"$set": {"items": items, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {"message": "Cart updated"}

class RemoveFromCartRequest(BaseModel):
    product_id: str
    size: str
    session_id: Optional[str] = None

@api_router.post("/cart/remove")
async def remove_from_cart(request: Request, body: RemoveFromCartRequest):
    """Remove item from cart"""
    user = await get_current_user(request)
    user_id = user.user_id if user else None
    
    query = {"user_id": user_id} if user_id else {"session_id": body.session_id}
    cart = await db.carts.find_one(query, {"_id": 0})
    
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    
    items = [i for i in cart.get("items", []) if not (i["product_id"] == body.product_id and i["size"] == body.size)]
    
    await db.carts.update_one(
        query,
        {"$set": {"items": items, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {"message": "Item removed"}

# ==================== WISHLIST ROUTES ====================

class WishlistRequest(BaseModel):
    product_id: str

@api_router.post("/wishlist/add")
async def add_to_wishlist(request: Request, body: WishlistRequest):
    """Add item to wishlist"""
    user = await require_auth(request)
    
    if body.product_id not in PRODUCTS:
        raise HTTPException(status_code=404, detail="Product not found")
    
    existing = await db.wishlists.find_one(
        {"user_id": user.user_id, "product_id": body.product_id},
        {"_id": 0}
    )
    
    if not existing:
        await db.wishlists.insert_one({
            "wishlist_id": f"wish_{uuid.uuid4().hex[:12]}",
            "user_id": user.user_id,
            "product_id": body.product_id,
            "added_at": datetime.now(timezone.utc).isoformat()
        })
    
    return {"message": "Added to wishlist"}

@api_router.post("/wishlist/remove")
async def remove_from_wishlist(request: Request, body: WishlistRequest):
    """Remove item from wishlist"""
    user = await require_auth(request)
    
    await db.wishlists.delete_one({
        "user_id": user.user_id,
        "product_id": body.product_id
    })
    
    return {"message": "Removed from wishlist"}

@api_router.get("/wishlist")
async def get_wishlist(request: Request):
    """Get user's wishlist"""
    user = await require_auth(request)
    
    wishlist_items = await db.wishlists.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).to_list(100)
    
    # Enrich with product data
    enriched_items = []
    for item in wishlist_items:
        product = PRODUCTS.get(item["product_id"])
        if product:
            enriched_items.append({
                **item,
                "product": product
            })
    
    return enriched_items

# ==================== ADDRESS ROUTES ====================

class AddressRequest(BaseModel):
    name: str
    street: str
    city: str
    state: str
    zip_code: str
    country: str = "United States"
    is_default: bool = False

@api_router.post("/addresses")
async def add_address(request: Request, body: AddressRequest):
    """Add new address"""
    user = await require_auth(request)
    
    if body.is_default:
        await db.addresses.update_many(
            {"user_id": user.user_id},
            {"$set": {"is_default": False}}
        )
    
    address = {
        "address_id": f"addr_{uuid.uuid4().hex[:12]}",
        "user_id": user.user_id,
        **body.model_dump(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.addresses.insert_one(address)
    
    return {"message": "Address added", "address_id": address["address_id"]}

@api_router.get("/addresses")
async def get_addresses(request: Request):
    """Get user's addresses"""
    user = await require_auth(request)
    
    addresses = await db.addresses.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).to_list(20)
    
    return addresses

@api_router.delete("/addresses/{address_id}")
async def delete_address(request: Request, address_id: str):
    """Delete address"""
    user = await require_auth(request)
    
    await db.addresses.delete_one({
        "address_id": address_id,
        "user_id": user.user_id
    })
    
    return {"message": "Address deleted"}

# ==================== ORDER ROUTES ====================

@api_router.get("/orders")
async def get_orders(request: Request):
    """Get user's orders"""
    user = await require_auth(request)
    
    orders = await db.orders.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    
    return orders

@api_router.get("/orders/{order_id}")
async def get_order(request: Request, order_id: str):
    """Get single order"""
    user = await require_auth(request)
    
    order = await db.orders.find_one(
        {"order_id": order_id, "user_id": user.user_id},
        {"_id": 0}
    )
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    return order

# ==================== CHECKOUT/PAYMENT ROUTES ====================

class CheckoutRequest(BaseModel):
    session_id: Optional[str] = None
    address_id: Optional[str] = None

@api_router.post("/checkout/create-session")
async def create_checkout_session(request: Request, body: CheckoutRequest):
    """Create Stripe checkout session"""
    user = await get_current_user(request)
    user_id = user.user_id if user else None
    
    # Get cart
    query = {"user_id": user_id} if user_id else {"session_id": body.session_id}
    cart = await db.carts.find_one(query, {"_id": 0})
    
    if not cart or not cart.get("items"):
        raise HTTPException(status_code=400, detail="Cart is empty")
    
    # Calculate total
    total = 0.0
    items_for_order = []
    for item in cart.get("items", []):
        product = PRODUCTS.get(item["product_id"])
        if product:
            total += product["price"] * item["quantity"]
            items_for_order.append({
                "product_id": item["product_id"],
                "name": product["name"],
                "price": product["price"],
                "quantity": item["quantity"],
                "size": item["size"],
                "url": product["url"]
            })
    
    # Get origin URL from request
    origin = request.headers.get("origin", request.headers.get("referer", "").rstrip("/"))
    if not origin:
        origin = str(request.base_url).rstrip("/")
    
    # Build URLs - REMINDER: DO NOT HARDCODE THE URL
    success_url = f"{origin}/checkout/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/cart"
    
    # Initialize Stripe
    host_url = str(request.base_url)
    webhook_url = f"{host_url}api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)
    
    # Create order first
    order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    
    metadata = {
        "order_id": order_id,
        "user_id": user_id or "guest",
        "cart_session": body.session_id or ""
    }
    
    # Create checkout session
    checkout_request = CheckoutSessionRequest(
        amount=total,
        currency="usd",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata
    )
    
    session: CheckoutSessionResponse = await stripe_checkout.create_checkout_session(checkout_request)
    
    # Create payment transaction record
    transaction = {
        "transaction_id": f"txn_{uuid.uuid4().hex[:12]}",
        "session_id": session.session_id,
        "user_id": user_id,
        "email": user.email if user else None,
        "amount": total,
        "currency": "usd",
        "status": "pending",
        "payment_status": "initiated",
        "metadata": metadata,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.payment_transactions.insert_one(transaction)
    
    # Create pending order
    order = {
        "order_id": order_id,
        "user_id": user_id,
        "items": items_for_order,
        "total": total,
        "status": "pending_payment",
        "payment_session_id": session.session_id,
        "shipping_address_id": body.address_id,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.orders.insert_one(order)
    
    return {"url": session.url, "session_id": session.session_id, "order_id": order_id}

@api_router.get("/checkout/status/{session_id}")
async def get_checkout_status(request: Request, session_id: str):
    """Get checkout session status and update order"""
    host_url = str(request.base_url)
    webhook_url = f"{host_url}api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)
    
    status: CheckoutStatusResponse = await stripe_checkout.get_checkout_status(session_id)
    
    # Update transaction status
    await db.payment_transactions.update_one(
        {"session_id": session_id},
        {"$set": {
            "status": status.status,
            "payment_status": status.payment_status,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    # If paid, update order and clear cart
    if status.payment_status == "paid":
        order = await db.orders.find_one({"payment_session_id": session_id}, {"_id": 0})
        if order and order.get("status") != "confirmed":
            await db.orders.update_one(
                {"payment_session_id": session_id},
                {"$set": {"status": "confirmed"}}
            )
            
            # Clear cart
            user_id = order.get("user_id")
            if user_id:
                await db.carts.delete_one({"user_id": user_id})
    
    return {
        "status": status.status,
        "payment_status": status.payment_status,
        "amount_total": status.amount_total,
        "currency": status.currency
    }

@api_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhooks"""
    try:
        body = await request.body()
        signature = request.headers.get("Stripe-Signature")
        
        host_url = str(request.base_url)
        webhook_url = f"{host_url}api/webhook/stripe"
        stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)
        
        webhook_response = await stripe_checkout.handle_webhook(body, signature)
        
        if webhook_response.payment_status == "paid":
            await db.payment_transactions.update_one(
                {"session_id": webhook_response.session_id},
                {"$set": {
                    "status": "completed",
                    "payment_status": "paid",
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            
            await db.orders.update_one(
                {"payment_session_id": webhook_response.session_id},
                {"$set": {"status": "confirmed"}}
            )
        
        return {"received": True}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"received": True}

# ==================== NEWSLETTER ROUTES ====================

class NewsletterRequest(BaseModel):
    email: str

@api_router.post("/newsletter/subscribe")
async def subscribe_newsletter(body: NewsletterRequest):
    """Subscribe to newsletter"""
    existing = await db.newsletter.find_one({"email": body.email}, {"_id": 0})
    
    if existing:
        return {"message": "Already subscribed"}
    
    subscription = {
        "subscription_id": f"sub_{uuid.uuid4().hex[:12]}",
        "email": body.email,
        "subscribed_at": datetime.now(timezone.utc).isoformat()
    }
    await db.newsletter.insert_one(subscription)
    
    return {"message": "Subscribed successfully"}

# ==================== BASIC ROUTES ====================

@api_router.get("/")
async def root():
    return {"message": "MONO API v1.0"}

# Include router
app.include_router(api_router)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
