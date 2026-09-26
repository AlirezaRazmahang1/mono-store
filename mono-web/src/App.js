import React, { useState, useEffect, createContext, useContext, useRef } from "react";
import "./App.css";
import { BrowserRouter, Routes, Route, useNavigate, useLocation, Link, useParams } from "react-router-dom";
import { Menu, X, ShoppingBag, ArrowRight, Instagram, Twitter, Heart, User, Package, MapPin, LogOut, Plus, Minus, Trash2, Check } from "lucide-react";
import { Toaster, toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// ==================== UI COMPONENTS (INLINE) ====================

const Button = ({ children, className = "", variant = "default", ...props }) => {
  const baseStyle = "px-6 py-3 font-body text-sm tracking-[0.2em] uppercase transition-all duration-300 flex items-center justify-center cursor-pointer";
  const variants = {
    default: "bg-white text-black hover:bg-white/90",
    outline: "border border-white/20 text-white hover:border-white/50"
  };
  return (
    <button className={`${baseStyle} ${variants[variant] || variants.default} ${className}`} {...props}>
      {children}
    </button>
  );
};

const Input = ({ className = "", ...props }) => {
  return (
    <input
      className={`w-full px-4 py-3 bg-transparent border border-white/20 text-white placeholder:text-white/40 focus:outline-none focus:border-white transition-colors ${className}`}
      {...props}
    />
  );
};

const Dialog = ({ open, onOpenChange, children }) => {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="relative w-full max-w-md bg-[#0A0A0A] border border-white/10 p-6 text-white">
        <button onClick={() => onOpenChange(false)} className="absolute top-4 right-4 text-white/60 hover:text-white">
          ✕
        </button>
        {children}
      </div>
    </div>
  );
};

const DialogContent = ({ children, className = "" }) => <div className={className}>{children}</div>;
const DialogHeader = ({ children }) => <div className="mb-4">{children}</div>;
const DialogTitle = ({ children, className = "" }) => <h2 className={`font-display text-2xl font-light ${className}`}>{children}</h2>;
const DialogDescription = ({ children, className = "" }) => <p className={`text-white/60 text-sm mt-2 ${className}`}>{children}</p>;


// ==================== CONTEXT ====================

const AuthContext = createContext(null);
const CartContext = createContext(null);

export const useAuth = () => useContext(AuthContext);
export const useCart = () => useContext(CartContext);

// ==================== AUTH PROVIDER ====================

const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const checkAuth = async () => {
    try {
      const res = await fetch(`${API}/auth/me`, { credentials: "include" });
      if (res.ok) {
        const userData = await res.json();
        setUser(userData);
      }
    } catch (e) {
      console.error("Auth check failed:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (window.location.hash?.includes("session_id=")) {
      setLoading(false);
      return;
    }
    checkAuth();
  }, []);

  const login = () => {
    const redirectUrl = window.location.origin + "/auth/callback";
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  const logout = async () => {
    await fetch(`${API}/auth/logout`, { method: "POST", credentials: "include" });
    setUser(null);
    window.location.href = "/";
  };

  return (
    <AuthContext.Provider value={{ user, setUser, loading, login, logout, checkAuth }}>
      {children}
    </AuthContext.Provider>
  );
};

// ==================== CART PROVIDER ====================

const CartProvider = ({ children }) => {
  const [cart, setCart] = useState({ items: [], total: 0 });
  const [cartSessionId, setCartSessionId] = useState(() => localStorage.getItem("cart_session_id") || null);

  const fetchCart = async () => {
    try {
      const res = await fetch(`${API}/cart`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ session_id: cartSessionId })
      });
      if (res.ok) {
        const data = await res.json();
        setCart(data);
      }
    } catch (e) {
      console.error("Failed to fetch cart:", e);
    }
  };

  useEffect(() => {
    fetchCart();
  }, [cartSessionId]);

  const addToCart = async (productId, quantity = 1, size = "M") => {
    try {
      const res = await fetch(`${API}/cart/add`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ product_id: productId, quantity, size, session_id: cartSessionId })
      });
      if (res.ok) {
        const data = await res.json();
        if (data.cart_session_id && !cartSessionId) {
          setCartSessionId(data.cart_session_id);
          localStorage.setItem("cart_session_id", data.cart_session_id);
        }
        fetchCart();
        toast.success("Added to cart");
      }
    } catch (e) {
      console.error("Failed to add to cart:", e);
      toast.error("Failed to add to cart");
    }
  };

  const updateCartItem = async (productId, size, quantity) => {
    try {
      await fetch(`${API}/cart/update`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ product_id: productId, size, quantity, session_id: cartSessionId })
      });
      fetchCart();
    } catch (e) {
      console.error("Failed to update cart:", e);
    }
  };

  const removeFromCart = async (productId, size) => {
    try {
      await fetch(`${API}/cart/remove`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ product_id: productId, size, session_id: cartSessionId })
      });
      fetchCart();
      toast.success("Removed from cart");
    } catch (e) {
      console.error("Failed to remove from cart:", e);
    }
  };

  const cartCount = cart.items.reduce((sum, item) => sum + item.quantity, 0);

  return (
    <CartContext.Provider value={{ cart, cartCount, cartSessionId, addToCart, updateCartItem, removeFromCart, fetchCart }}>
      {children}
    </CartContext.Provider>
  );
};

// ==================== PRODUCTS DATA ====================

const products = [
  {
    id: "hoodie-1",
    name: "Venom Oversized Hoodie",
    type: "Hoodie",
    category: "men",
    price: 450,
    description: "Premium heavyweight oversized hoodie with hidden kangaroo pocket. Crafted from 100% organic cotton with a serpentine-inspired silhouette.",
    sizes: ["XS", "S", "M", "L", "XL", "XXL"],
    url: "https://images.unsplash.com/photo-1647768617268-06697e8a91d4?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxOTJ8MHwxfHNlYXJjaHwxfHxibGFjayUyMGhvb2RpZSUyMGZhc2hpb24lMjBtb2RlbCUyMGRhcmt8ZW58MHx8fHwxNzc0NTU4OTQ2fDA&ixlib=rb-4.1.0&q=85",
    featured: true
  },
  {
    id: "hoodie-2",
    name: "Coil Heavyweight Hoodie",
    type: "Hoodie",
    category: "women",
    price: 480,
    description: "Double-layered heavyweight construction with matte black hardware. Features extended sleeves and dropped shoulders.",
    sizes: ["XS", "S", "M", "L", "XL", "XXL"],
    url: "https://images.pexels.com/photos/3894527/pexels-photo-3894527.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"
  },
  {
    id: "pants-1",
    name: "Mamba Leather Trousers",
    type: "Pants",
    category: "men",
    price: 850,
    description: "Full-grain leather trousers with scaled texture detailing. Tailored fit with concealed zip closure.",
    sizes: ["XS", "S", "M", "L", "XL"],
    url: "https://images.unsplash.com/photo-1762522926410-9bf43dc9c9e5?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxODd8MHwxfHNlYXJjaHwyfHxibGFjayUyMHBhbnRzJTIwZmFzaGlvbiUyMGRhcmt8ZW58MHx8fHwxNzc0NTU4OTMyfDA&ixlib=rb-4.1.0&q=85"
  },
  {
    id: "pants-2",
    name: "Shed Cargo Pants",
    type: "Pants",
    category: "women",
    price: 620,
    description: "Technical cargo pants with modular pocket system. Water-resistant fabric with articulated knees.",
    sizes: ["XS", "S", "M", "L", "XL", "XXL"],
    url: "https://images.pexels.com/photos/5427206/pexels-photo-5427206.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"
  },
  {
    id: "tshirt-1",
    name: "Fangs Boxy Tee",
    type: "T-shirt",
    category: "men",
    price: 220,
    description: "Oversized boxy silhouette tee in heavyweight cotton. Features subtle embossed logo at back neck.",
    sizes: ["XS", "S", "M", "L", "XL", "XXL"],
    url: "https://images.unsplash.com/photo-1762914395034-67c2f8c73c59?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxODd8MHwxfHNlYXJjaHwyfHxibGFjayUyMHN0cmVldHdlYXIlMjBtb2RlbCUyMGRhcmt8ZW58MHx8fHwxNzc0NTU4OTMyfDA&ixlib=rb-4.1.0&q=85"
  }
];

// ==================== NEWSLETTER POPUP ====================

const NewsletterPopup = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
    const hasSeenPopup = localStorage.getItem("mono_newsletter_seen");
    if (!hasSeenPopup) {
      const timer = setTimeout(() => setIsOpen(true), 3000);
      return () => clearTimeout(timer);
    }
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await fetch(`${API}/newsletter/subscribe`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email })
      });
      setSubmitted(true);
      localStorage.setItem("mono_newsletter_seen", "true");
      setTimeout(() => setIsOpen(false), 2000);
    } catch (e) {
      toast.error("Failed to subscribe");
    }
  };

  const handleClose = () => {
    setIsOpen(false);
    localStorage.setItem("mono_newsletter_seen", "true");
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="bg-[#0A0A0A] border border-white/10 text-white max-w-md" data-testid="newsletter-popup">
        <DialogHeader>
          <DialogTitle className="font-display text-3xl tracking-tighter font-light">
            Join the Void
          </DialogTitle>
          <DialogDescription className="text-white/60 font-body">
            Subscribe for exclusive drops, early access, and 10% off your first order.
          </DialogDescription>
        </DialogHeader>
        {submitted ? (
          <div className="py-8 text-center">
            <Check className="mx-auto mb-4 text-white" size={48} />
            <p className="font-body text-lg">Welcome to MONO</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4 mt-4">
            <Input
              type="email"
              placeholder="Enter your email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="bg-transparent border-white/20 text-white placeholder:text-white/40 rounded-none"
              data-testid="newsletter-email-input"
            />
            <Button 
              type="submit" 
              className="w-full btn-primary rounded-none"
              data-testid="newsletter-submit-btn"
            >
              Subscribe
            </Button>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
};

// ==================== NAVIGATION ====================

const Navigation = () => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const { user, login, logout } = useAuth();
  const { cartCount } = useCart();
  const navigate = useNavigate();

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 50);
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <nav
      data-testid="main-navigation"
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-500 ${
        scrolled ? "nav-glass py-4" : "bg-transparent py-6"
      }`}
    >
      <div className="max-w-7xl mx-auto px-6 sm:px-12 flex items-center justify-between">
        <Link to="/" data-testid="nav-logo" className="font-display text-2xl sm:text-3xl tracking-tighter font-medium text-white">
          MONO
        </Link>

        <div className="hidden md:flex items-center gap-12">
          <Link to="/shop" data-testid="nav-link-shop" className="font-body text-sm tracking-[0.2em] uppercase text-white/60 hover:text-white transition-colors duration-300">
            Shop
          </Link>
          <Link to="/shop?category=men" className="font-body text-sm tracking-[0.2em] uppercase text-white/60 hover:text-white transition-colors duration-300">
            Men
          </Link>
          <Link to="/shop?category=women" className="font-body text-sm tracking-[0.2em] uppercase text-white/60 hover:text-white transition-colors duration-300">
            Women
          </Link>
          <a href="/#about" data-testid="nav-link-about" className="font-body text-sm tracking-[0.2em] uppercase text-white/60 hover:text-white transition-colors duration-300">
            About
          </a>
        </div>

        <div className="flex items-center gap-4">
          {user ? (
            <button
              data-testid="user-menu-btn"
              onClick={() => navigate("/account")}
              className="p-2 text-white/80 hover:text-white transition-colors"
            >
              <User size={22} />
            </button>
          ) : (
            <button
              data-testid="login-btn"
              onClick={login}
              className="hidden sm:block font-body text-sm tracking-[0.2em] uppercase text-white/60 hover:text-white transition-colors"
            >
              Sign In
            </button>
          )}

          <button
            data-testid="cart-button"
            onClick={() => navigate("/cart")}
            className="relative p-2 text-white/80 hover:text-white transition-colors"
          >
            <ShoppingBag size={22} />
            <span className="absolute -top-1 -right-1 w-4 h-4 bg-white text-black text-[10px] flex items-center justify-center font-medium">
              {cartCount}
            </span>
          </button>

          <button
            data-testid="mobile-menu-toggle"
            className="md:hidden p-2 text-white"
            onClick={() => setIsMenuOpen(!isMenuOpen)}
          >
            {isMenuOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>
      </div>

      {isMenuOpen && (
        <div data-testid="mobile-menu" className="md:hidden absolute top-full left-0 right-0 nav-glass border-t border-white/10">
          <div className="px-6 py-8 flex flex-col gap-6">
            <Link to="/shop" className="font-body text-lg tracking-[0.15em] uppercase text-white/80 hover:text-white" onClick={() => setIsMenuOpen(false)}>
              Shop
            </Link>
            <Link to="/shop?category=men" className="font-body text-lg tracking-[0.15em] uppercase text-white/80 hover:text-white" onClick={() => setIsMenuOpen(false)}>
              Men
            </Link>
            <Link to="/shop?category=women" className="font-body text-lg tracking-[0.15em] uppercase text-white/80 hover:text-white" onClick={() => setIsMenuOpen(false)}>
              Women
            </Link>
            <a href="/#about" className="font-body text-lg tracking-[0.15em] uppercase text-white/80 hover:text-white" onClick={() => setIsMenuOpen(false)}>
              About
            </a>
            {user ? (
              <>
                <Link to="/account" className="font-body text-lg tracking-[0.15em] uppercase text-white/80 hover:text-white" onClick={() => setIsMenuOpen(false)}>
                  Account
                </Link>
                <button onClick={logout} className="font-body text-lg tracking-[0.15em] uppercase text-white/80 hover:text-white text-left">
                  Logout
                </button>
              </>
            ) : (
              <button onClick={login} className="font-body text-lg tracking-[0.15em] uppercase text-white/80 hover:text-white text-left">
                Sign In
              </button>
            )}
          </div>
        </div>
      )}
    </nav>
  );
};

// ==================== HOME PAGE ====================

const HeroSection = () => {
  const navigate = useNavigate();
  
  return (
    <section data-testid="hero-section" className="relative min-h-screen flex items-end pb-24 sm:pb-32">
      <div className="absolute inset-0 z-0">
        <img
          src="https://images.pexels.com/photos/5922856/pexels-photo-5922856.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"
          alt="Snake texture"
          className="w-full h-full object-cover opacity-40"
        />
        <div className="absolute inset-0 hero-gradient" />
      </div>

      <div className="relative z-10 max-w-7xl mx-auto px-6 sm:px-12 w-full">
        <div className="max-w-4xl">
          <p data-testid="hero-label" className="font-body uppercase tracking-[0.3em] text-xs text-white/60 mb-6">
            FW25 Collection
          </p>
          <h1 data-testid="hero-title" className="font-display text-5xl sm:text-6xl lg:text-8xl tracking-tighter font-light text-white leading-[0.9]">
            The Dawn of
            <br />
            <span className="italic">Shedding</span>
          </h1>
          <p data-testid="hero-description" className="font-body text-lg sm:text-xl text-white/60 mt-8 max-w-lg font-light leading-relaxed">
            Luxury streetwear forged in darkness. Where minimalism meets raw expression.
          </p>
          <div className="flex flex-wrap gap-4 mt-10">
            <Button data-testid="hero-cta-primary" className="btn-primary rounded-none" onClick={() => navigate("/shop")}>
              Explore Collection
            </Button>
            <Button data-testid="hero-cta-secondary" variant="outline" className="btn-outline rounded-none" onClick={() => document.getElementById("about")?.scrollIntoView({ behavior: "smooth" })}>
              Our Story
            </Button>
          </div>
        </div>
      </div>

      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 z-10">
        <div className="w-[1px] h-16 bg-gradient-to-b from-transparent via-white/30 to-white/60 animate-pulse" />
      </div>
    </section>
  );
};

const ProductCard = ({ product, index, className = "" }) => {
  const [imageLoaded, setImageLoaded] = useState(false);
  const { addToCart } = useCart();
  const navigate = useNavigate();

  return (
    <div
      data-testid={`product-card-${product.id}`}
      className={`product-card group relative overflow-hidden border border-white/10 bg-[#0A0A0A] flex flex-col page-transition stagger-${index + 1} ${className}`}
    >
      <div className="relative w-full aspect-[3/4] overflow-hidden bg-[#141414] cursor-pointer" onClick={() => navigate(`/product/${product.id}`)}>
        {!imageLoaded && <div className="absolute inset-0 image-loading" />}
        <img
          src={product.url}
          alt={product.name}
          className={`product-image w-full h-full object-cover object-center ${imageLoaded ? "opacity-80" : "opacity-0"}`}
          onLoad={() => setImageLoaded(true)}
        />
        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors duration-500" />
        
        <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity duration-500 gap-3">
          <Button data-testid={`quick-add-${product.id}`} className="btn-primary rounded-none text-xs py-3 px-6" onClick={(e) => { e.stopPropagation(); addToCart(product.id); }}>
            Add to Cart
          </Button>
        </div>
      </div>

      <div className="p-6 flex justify-between items-end">
        <div>
          <span className="font-body text-[10px] uppercase tracking-[0.2em] text-white/40 block mb-1">{product.type}</span>
          <h3 data-testid={`product-name-${product.id}`} className="font-display text-lg tracking-tight text-white">{product.name}</h3>
        </div>
        <span data-testid={`product-price-${product.id}`} className="font-body text-sm tracking-widest text-white/60">${product.price}</span>
      </div>
    </div>
  );
};

const CollectionSection = () => {
  const navigate = useNavigate();
  
  return (
    <section id="collection" data-testid="collection-section" className="py-24 sm:py-32 bg-[#050505]">
      <div className="max-w-7xl mx-auto px-6 sm:px-12">
        <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between mb-16 gap-6">
          <div>
            <p className="font-body uppercase tracking-[0.3em] text-xs text-white/40 mb-4">New Arrivals</p>
            <h2 data-testid="collection-title" className="font-display text-3xl sm:text-4xl lg:text-5xl tracking-tighter font-light text-white">
              The Collection
            </h2>
          </div>
          <button onClick={() => navigate("/shop")} data-testid="view-all-link" className="group flex items-center gap-2 font-body text-sm uppercase tracking-[0.2em] text-white/60 hover:text-white transition-colors">
            View All
            <ArrowRight size={16} className="group-hover:translate-x-1 transition-transform" />
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 sm:gap-8">
          <div className="lg:row-span-2">
            <ProductCard product={products[0]} index={0} className="h-full" />
          </div>
          <ProductCard product={products[1]} index={1} />
          <ProductCard product={products[2]} index={2} />
          <div className="sm:col-span-2 lg:col-span-2 grid grid-cols-1 sm:grid-cols-2 gap-6 sm:gap-8">
            <ProductCard product={products[3]} index={3} />
            <ProductCard product={products[4]} index={4} />
          </div>
        </div>
      </div>
    </section>
  );
};

const MarqueeSection = () => {
  const marqueeText = "MONO — LUXURY — AVANT-GARDE — STREETWEAR — DARKNESS — ";

  return (
    <div data-testid="marquee-section" className="py-12 bg-[#0A0A0A] border-y border-white/5 overflow-hidden">
      <div className="marquee-container">
        <div className="marquee-content animate-marquee">
          {[...Array(4)].map((_, i) => (
            <span key={i} className="font-display text-4xl sm:text-5xl lg:text-6xl tracking-tighter text-white/10 whitespace-nowrap">
              {marqueeText}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
};

const AboutSection = () => {
  return (
    <section id="about" data-testid="about-section" className="py-24 sm:py-32 bg-[#050505]">
      <div className="max-w-7xl mx-auto px-6 sm:px-12">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 lg:gap-24 items-center">
          <div className="about-image-container order-2 lg:order-1">
            <img
              src="https://images.pexels.com/photos/5365452/pexels-photo-5365452.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"
              alt="MONO brand aesthetic"
              data-testid="about-image"
              className="w-full aspect-[4/5] object-cover opacity-90"
            />
          </div>

          <div className="order-1 lg:order-2">
            <p className="font-body uppercase tracking-[0.3em] text-xs text-white/40 mb-6">Our Story</p>
            <h2 data-testid="about-title" className="font-display text-3xl sm:text-4xl lg:text-5xl tracking-tighter font-light text-white leading-[1.1] mb-8">
              Forged in
              <br />
              <span className="italic">the fracture</span>
            </h2>
            <p data-testid="about-description" className="font-body text-base sm:text-lg text-white/60 font-light leading-relaxed mb-6">
              True creation often requires the courage to destroy. MONO was not inherited; it was forged in the fracture of a fading lineage. When a family legacy collapsed under the weight of its own rigid traditions, we found ourselves standing in the shadows of what could have been. The doors were closed to us, so we built our own house.
            </p>
            <p className="font-body text-base sm:text-lg text-white/60 font-light leading-relaxed mb-6">
              We took the ruin and made it our raw material. MONO is the alchemy of hardship translated into uncompromising design. It is the physical manifestation of the dawn of shedding—stripping away the constraints of the past to breathe life into a new, sovereign vision by our own hands.
            </p>
            <p className="font-body text-base sm:text-lg text-white/60 font-light leading-relaxed mb-10">
              Every heavy seam, hidden zipper, and tailored shadow is a testament to this rebirth. We do not just make garments; we construct armor for the metamorphosis. MONO is crafted for those who have navigated their own void, shed their history, and emerged entirely their own.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
};

const Footer = () => {
  return (
    <footer id="contact" data-testid="footer" className="py-16 sm:py-24 bg-[#0A0A0A] border-t border-white/10">
      <div className="max-w-7xl mx-auto px-6 sm:px-12">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-12 mb-16">
          <div className="md:col-span-2">
            <h3 data-testid="footer-logo" className="font-display text-3xl tracking-tighter font-medium text-white mb-4">MONO</h3>
            <p className="font-body text-sm text-white/50 max-w-xs leading-relaxed">
              Luxury streetwear for the modern void dweller. Monochromatic excellence since 2024.
            </p>
            <div className="flex gap-4 mt-6">
              <a href="#" data-testid="social-instagram" className="p-2 border border-white/10 text-white/50 hover:text-white hover:border-white/30 transition-all">
                <Instagram size={18} />
              </a>
              <a href="#" data-testid="social-twitter" className="p-2 border border-white/10 text-white/50 hover:text-white hover:border-white/30 transition-all">
                <Twitter size={18} />
              </a>
            </div>
          </div>

          <div>
            <h4 className="font-body uppercase tracking-[0.2em] text-xs text-white mb-6">Shop</h4>
            <ul className="space-y-3">
              <li><Link to="/shop" className="footer-link font-body text-sm">All Products</Link></li>
              <li><Link to="/shop?category=men" className="footer-link font-body text-sm">Men</Link></li>
              <li><Link to="/shop?category=women" className="footer-link font-body text-sm">Women</Link></li>
              <li><Link to="/shop?type=Hoodie" className="footer-link font-body text-sm">Hoodies</Link></li>
            </ul>
          </div>

          <div>
            <h4 className="font-body uppercase tracking-[0.2em] text-xs text-white mb-6">Info</h4>
            <ul className="space-y-3">
              <li><a href="/#about" className="footer-link font-body text-sm">About Us</a></li>
              <li><a href="#" className="footer-link font-body text-sm">Shipping</a></li>
              <li><a href="#" className="footer-link font-body text-sm">Returns</a></li>
              <li><a href="#" className="footer-link font-body text-sm">Contact</a></li>
            </ul>
          </div>
        </div>

        <div className="pt-8 border-t border-white/10 flex flex-col sm:flex-row justify-between items-center gap-4">
          <p className="font-body text-xs text-white/30">© 2025 MONO. All rights reserved.</p>
          <div className="flex gap-6">
            <a href="#" className="font-body text-xs text-white/30 hover:text-white/60 transition-colors">Privacy Policy</a>
            <a href="#" className="font-body text-xs text-white/30 hover:text-white/60 transition-colors">Terms of Service</a>
          </div>
        </div>
      </div>
    </footer>
  );
};

const HomePage = () => (
  <>
    <HeroSection />
    <MarqueeSection />
    <CollectionSection />
    <AboutSection />
  </>
);

// ==================== SHOP PAGE ====================

const ShopPage = () => {
  const [filter, setFilter] = useState("all");
  const location = useLocation();

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const category = params.get("category");
    const type = params.get("type");
    if (category) setFilter(category);
    else if (type) setFilter(type);
  }, [location]);

  const filteredProducts = filter === "all" 
    ? products 
    : products.filter(p => p.category === filter || p.type === filter);

  return (
    <div className="pt-32 pb-24 bg-[#050505] min-h-screen">
      <div className="max-w-7xl mx-auto px-6 sm:px-12">
        <h1 className="font-display text-4xl sm:text-5xl tracking-tighter font-light text-white mb-12">Shop</h1>
        
        <div className="flex gap-4 mb-12 flex-wrap">
          {["all", "men", "women", "Hoodie", "Pants", "T-shirt"].map(type => (
            <button
              key={type}
              onClick={() => setFilter(type)}
              className={`font-body text-sm uppercase tracking-[0.2em] px-4 py-2 border transition-colors ${
                filter === type ? "bg-white text-black border-white" : "border-white/20 text-white/60 hover:border-white/40"
              }`}
              data-testid={`filter-${type}`}
            >
              {type === "all" ? "All Products" : type.toUpperCase()}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 sm:gap-8">
          {filteredProducts.map((product, index) => (
            <ProductCard key={product.id} product={product} index={index} />
          ))}
        </div>
      </div>
    </div>
  );
};

// ==================== PRODUCT DETAIL PAGE ====================

const ProductDetailPage = () => {
  const { id } = useParams();
  const product = products.find(p => p.id === id);
  const [selectedSize, setSelectedSize] = useState("M");
  const [quantity, setQuantity] = useState(1);
  const { addToCart } = useCart();
  const { user, login } = useAuth();

  if (!product) {
    return (
      <div className="pt-32 pb-24 bg-[#050505] min-h-screen text-center">
        <p className="text-white/60">Product not found</p>
      </div>
    );
  }

  const handleAddToWishlist = async () => {
    if (!user) {
      login();
      return;
    }
    try {
      await fetch(`${API}/wishlist/add`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ product_id: product.id })
      });
      toast.success("Added to wishlist");
    } catch (e) {
      toast.error("Failed to add to wishlist");
    }
  };

  return (
    <div className="pt-32 pb-24 bg-[#050505] min-h-screen">
      <div className="max-w-7xl mx-auto px-6 sm:px-12">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-24">
          <div className="aspect-[3/4] bg-[#0A0A0A] border border-white/10">
            <img src={product.url} alt={product.name} className="w-full h-full object-cover opacity-90" />
          </div>

          <div className="flex flex-col justify-center">
            <p className="font-body uppercase tracking-[0.3em] text-xs text-white/40 mb-2">{product.type}</p>
            <h1 className="font-display text-4xl sm:text-5xl tracking-tighter font-light text-white mb-4" data-testid="product-detail-name">
              {product.name}
            </h1>
            <p className="font-body text-2xl text-white/80 mb-8" data-testid="product-detail-price">${product.price}</p>
            <p className="font-body text-white/60 leading-relaxed mb-8">{product.description}</p>

            <div className="mb-8">
              <p className="font-body uppercase tracking-[0.2em] text-xs text-white/60 mb-4">Size</p>
              <div className="flex flex-wrap gap-3">
                {product.sizes.map(size => (
                  <button
                    key={size}
                    onClick={() => setSelectedSize(size)}
                    className={`w-12 h-12 border font-body text-sm transition-colors ${
                      selectedSize === size ? "bg-white text-black border-white" : "border-white/20 text-white/60 hover:border-white/40"
                    }`}
                    data-testid={`size-${size}`}
                  >
                    {size}
                  </button>
                ))}
              </div>
            </div>

            <div className="mb-8">
              <p className="font-body uppercase tracking-[0.2em] text-xs text-white/60 mb-4">Quantity</p>
              <div className="flex items-center gap-4">
                <button
                  onClick={() => setQuantity(Math.max(1, quantity - 1))}
                  className="w-10 h-10 border border-white/20 flex items-center justify-center text-white/60 hover:border-white/40"
                >
                  <Minus size={16} />
                </button>
                <span className="font-body text-lg text-white w-8 text-center">{quantity}</span>
                <button
                  onClick={() => setQuantity(quantity + 1)}
                  className="w-10 h-10 border border-white/20 flex items-center justify-center text-white/60 hover:border-white/40"
                >
                  <Plus size={16} />
                </button>
              </div>
            </div>

            <div className="flex gap-4">
              <Button
                className="flex-1 btn-primary rounded-none"
                onClick={() => addToCart(product.id, quantity, selectedSize)}
                data-testid="add-to-cart-btn"
              >
                Add to Cart
              </Button>
              <button
                onClick={handleAddToWishlist}
                className="w-14 h-14 border border-white/20 flex items-center justify-center text-white/60 hover:border-white/40 transition-colors"
                data-testid="add-to-wishlist-btn"
              >
                <Heart size={20} />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// ==================== CART PAGE ====================

const CartPage = () => {
  const { cart, updateCartItem, removeFromCart, cartSessionId } = useCart();
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  const handleCheckout = async () => {
    if (!user) {
      toast.error("Please sign in to checkout");
      login();
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${API}/checkout/create-session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ session_id: cartSessionId })
      });
      
      if (res.ok) {
        const data = await res.json();
        window.location.href = data.url;
      } else {
        toast.error("Failed to create checkout session");
      }
    } catch (e) {
      toast.error("Checkout failed");
    } finally {
      setLoading(false);
    }
  };

  if (cart.items.length === 0) {
    return (
      <div className="pt-32 pb-24 bg-[#050505] min-h-screen">
        <div className="max-w-7xl mx-auto px-6 sm:px-12 text-center">
          <ShoppingBag size={64} className="mx-auto mb-6 text-white/20" />
          <h1 className="font-display text-3xl tracking-tighter text-white mb-4">Your cart is empty</h1>
          <p className="font-body text-white/60 mb-8">Explore our collection and add some pieces.</p>
          <Button onClick={() => navigate("/shop")} className="btn-primary rounded-none">
            Continue Shopping
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="pt-32 pb-24 bg-[#050505] min-h-screen">
      <div className="max-w-7xl mx-auto px-6 sm:px-12">
        <h1 className="font-display text-4xl sm:text-5xl tracking-tighter font-light text-white mb-12">Cart</h1>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-12">
          <div className="lg:col-span-2 space-y-6">
            {cart.items.map((item, index) => (
              <div key={`${item.product_id}-${item.size}`} className="flex gap-6 p-6 bg-[#0A0A0A] border border-white/10" data-testid={`cart-item-${index}`}>
                <div className="w-24 h-32 bg-[#141414] flex-shrink-0">
                  <img src={item.url} alt={item.name} className="w-full h-full object-cover opacity-80" />
                </div>
                <div className="flex-1">
                  <div className="flex justify-between">
                    <div>
                      <p className="font-body text-[10px] uppercase tracking-[0.2em] text-white/40 mb-1">{item.type}</p>
                      <h3 className="font-display text-lg text-white">{item.name}</h3>
                      <p className="font-body text-sm text-white/60 mt-1">Size: {item.size}</p>
                    </div>
                    <button onClick={() => removeFromCart(item.product_id, item.size)} className="text-white/40 hover:text-white">
                      <Trash2 size={18} />
                    </button>
                  </div>
                  <div className="flex justify-between items-end mt-4">
                    <div className="flex items-center gap-3">
                      <button
                        onClick={() => updateCartItem(item.product_id, item.size, item.quantity - 1)}
                        className="w-8 h-8 border border-white/20 flex items-center justify-center text-white/60"
                      >
                        <Minus size={14} />
                      </button>
                      <span className="font-body text-white w-6 text-center">{item.quantity}</span>
                      <button
                        onClick={() => updateCartItem(item.product_id, item.size, item.quantity + 1)}
                        className="w-8 h-8 border border-white/20 flex items-center justify-center text-white/60"
                      >
                        <Plus size={14} />
                      </button>
                    </div>
                    <p className="font-body text-white">${(item.price * item.quantity).toFixed(2)}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="lg:col-span-1">
            <div className="bg-[#0A0A0A] border border-white/10 p-6 sticky top-32">
              <h2 className="font-display text-xl text-white mb-6">Order Summary</h2>
              <div className="space-y-3 mb-6">
                <div className="flex justify-between font-body text-white/60">
                  <span>Subtotal</span>
                  <span>${cart.total.toFixed(2)}</span>
                </div>
                <div className="flex justify-between font-body text-white/60">
                  <span>Shipping</span>
                  <span>Calculated at checkout</span>
                </div>
              </div>
              <div className="border-t border-white/10 pt-4 mb-6">
                <div className="flex justify-between font-body text-lg text-white">
                  <span>Total</span>
                  <span>${cart.total.toFixed(2)}</span>
                </div>
              </div>
              <Button
                onClick={handleCheckout}
                disabled={loading}
                className="w-full btn-primary rounded-none"
                data-testid="checkout-btn"
              >
                {loading ? "Processing..." : "Proceed to Checkout"}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// ==================== CHECKOUT SUCCESS PAGE ====================

const CheckoutSuccessPage = () => {
  const [status, setStatus] = useState("checking");
  const location = useLocation();
  const navigate = useNavigate();
  const hasPolled = useRef(false);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const sessionId = params.get("session_id");

    if (!sessionId || hasPolled.current) return;
    hasPolled.current = true;

    const pollStatus = async (attempts = 0) => {
      const maxAttempts = 5;
      const pollInterval = 2000;

      if (attempts >= maxAttempts) {
        setStatus("timeout");
        return;
      }

      try {
        const res = await fetch(`${API}/checkout/status/${sessionId}`, { credentials: "include" });
        if (!res.ok) throw new Error("Failed to check status");
        
        const data = await res.json();
        
        if (data.payment_status === "paid") {
          setStatus("success");
          return;
        } else if (data.status === "expired") {
          setStatus("expired");
          return;
        }

        setTimeout(() => pollStatus(attempts + 1), pollInterval);
      } catch (e) {
        setStatus("error");
      }
    };

    pollStatus();
  }, [location]);

  return (
    <div className="pt-32 pb-24 bg-[#050505] min-h-screen">
      <div className="max-w-lg mx-auto px-6 text-center">
        {status === "checking" && (
          <>
            <div className="w-16 h-16 border-2 border-white/20 border-t-white rounded-full animate-spin mx-auto mb-6" />
            <h1 className="font-display text-3xl text-white mb-4">Processing Payment</h1>
            <p className="font-body text-white/60">Please wait while we confirm your payment...</p>
          </>
        )}

        {status === "success" && (
          <>
            <Check size={64} className="mx-auto mb-6 text-green-500" />
            <h1 className="font-display text-3xl text-white mb-4">Order Confirmed</h1>
            <p className="font-body text-white/60 mb-8">Thank you for your purchase. You will receive an email confirmation shortly.</p>
            <Button onClick={() => navigate("/account")} className="btn-primary rounded-none">
              View Orders
            </Button>
          </>
        )}

        {(status === "error" || status === "timeout" || status === "expired") && (
          <>
            <X size={64} className="mx-auto mb-6 text-red-500" />
            <h1 className="font-display text-3xl text-white mb-4">Payment Failed</h1>
            <p className="font-body text-white/60 mb-8">There was an issue processing your payment. Please try again.</p>
            <Button onClick={() => navigate("/cart")} className="btn-primary rounded-none">
              Return to Cart
            </Button>
          </>
        )}
      </div>
    </div>
  );
};

// ==================== ACCOUNT PAGE ====================

const AccountPage = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState("orders");
  const [orders, setOrders] = useState([]);
  const [wishlist, setWishlist] = useState([]);
  const [addresses, setAddresses] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) {
      navigate("/");
      return;
    }
    fetchData();
  }, [user, activeTab]);

  const fetchData = async () => {
    setLoading(true);
    try {
      if (activeTab === "orders") {
        const res = await fetch(`${API}/orders`, { credentials: "include" });
        if (res.ok) setOrders(await res.json());
      } else if (activeTab === "wishlist") {
        const res = await fetch(`${API}/wishlist`, { credentials: "include" });
        if (res.ok) setWishlist(await res.json());
      } else if (activeTab === "addresses") {
        const res = await fetch(`${API}/addresses`, { credentials: "include" });
        if (res.ok) setAddresses(await res.json());
      }
    } catch (e) {
      console.error("Failed to fetch data:", e);
    }
    setLoading(false);
  };

  const tabs = [
    { id: "orders", label: "Orders", icon: Package },
    { id: "wishlist", label: "Wishlist", icon: Heart },
    { id: "addresses", label: "Addresses", icon: MapPin }
  ];

  if (!user) return null;

  return (
    <div className="pt-32 pb-24 bg-[#050505] min-h-screen">
      <div className="max-w-7xl mx-auto px-6 sm:px-12">
        <div className="flex justify-between items-center mb-12">
          <div>
            <h1 className="font-display text-4xl sm:text-5xl tracking-tighter font-light text-white">Account</h1>
            <p className="font-body text-white/60 mt-2">Welcome back, {user.name}</p>
          </div>
          <Button onClick={logout} variant="outline" className="btn-outline rounded-none gap-2">
            <LogOut size={16} />
            Logout
          </Button>
        </div>

        <div className="flex gap-6 mb-8 border-b border-white/10">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 pb-4 font-body text-sm uppercase tracking-[0.2em] transition-colors ${
                activeTab === tab.id ? "text-white border-b-2 border-white" : "text-white/40 hover:text-white/60"
              }`}
              data-testid={`tab-${tab.id}`}
            >
              <tab.icon size={16} />
              {tab.label}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="text-center py-12">
            <div className="w-8 h-8 border-2 border-white/20 border-t-white rounded-full animate-spin mx-auto" />
          </div>
        ) : (
          <>
            {activeTab === "orders" && (
              <div className="space-y-4">
                {orders.length === 0 ? (
                  <p className="text-white/60 text-center py-12">No orders yet</p>
                ) : (
                  orders.map(order => (
                    <div key={order.order_id} className="bg-[#0A0A0A] border border-white/10 p-6">
                      <div className="flex justify-between items-start mb-4">
                        <div>
                          <p className="font-body text-xs text-white/40 uppercase tracking-wider">Order {order.order_id}</p>
                          <p className="font-body text-sm text-white/60 mt-1">
                            {new Date(order.created_at).toLocaleDateString()}
                          </p>
                        </div>
                        <span className={`px-3 py-1 text-xs uppercase tracking-wider ${
                          order.status === "confirmed" ? "bg-green-500/20 text-green-400" : "bg-yellow-500/20 text-yellow-400"
                        }`}>
                          {order.status}
                        </span>
                      </div>
                      <div className="flex gap-4 overflow-x-auto">
                        {order.items.map((item, i) => (
                          <div key={i} className="w-16 h-20 bg-[#141414] flex-shrink-0">
                            <img src={item.url} alt={item.name} className="w-full h-full object-cover opacity-80" />
                          </div>
                        ))}
                      </div>
                      <p className="font-body text-white mt-4">Total: ${order.total.toFixed(2)}</p>
                    </div>
                  ))
                )}
              </div>
            )}

            {activeTab === "wishlist" && (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
                {wishlist.length === 0 ? (
                  <p className="text-white/60 text-center py-12 col-span-full">No items in wishlist</p>
                ) : (
                  wishlist.map(item => (
                    <ProductCard key={item.product_id} product={item.product} index={0} />
                  ))
                )}
              </div>
            )}

            {activeTab === "addresses" && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                {addresses.map(addr => (
                  <div key={addr.address_id} className="bg-[#0A0A0A] border border-white/10 p-6">
                    <p className="font-body text-white">{addr.name}</p>
                    <p className="font-body text-white/60 text-sm mt-2">{addr.street}</p>
                    <p className="font-body text-white/60 text-sm">{addr.city}, {addr.state} {addr.zip_code}</p>
                    <p className="font-body text-white/60 text-sm">{addr.country}</p>
                    {addr.is_default && (
                      <span className="inline-block mt-3 px-2 py-1 bg-white/10 text-white/60 text-xs uppercase tracking-wider">
                        Default
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

// ==================== AUTH CALLBACK ====================

const AuthCallback = () => {
  const { setUser } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const hasProcessed = useRef(false);

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const processAuth = async () => {
      const hash = location.hash;
      const sessionIdMatch = hash.match(/session_id=([^&]+)/);
      
      if (!sessionIdMatch) {
        navigate("/");
        return;
      }

      const sessionId = sessionIdMatch[1];

      try {
        const res = await fetch(`${API}/auth/session`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ session_id: sessionId })
        });

        if (res.ok) {
          const user = await res.json();
          setUser(user);
          navigate("/", { state: { user } });
        } else {
          navigate("/");
        }
      } catch (e) {
        console.error("Auth callback failed:", e);
        navigate("/");
      }
    };

    processAuth();
  }, []);

  return (
    <div className="min-h-screen bg-[#050505] flex items-center justify-center">
      <div className="text-center">
        <div className="w-8 h-8 border-2 border-white/20 border-t-white rounded-full animate-spin mx-auto mb-4" />
        <p className="font-body text-white/60">Signing you in...</p>
      </div>
    </div>
  );
};

// ==================== APP ROUTER ====================

const AppRouter = () => {
  const location = useLocation();
  
  if (location.hash?.includes("session_id=")) {
    return <AuthCallback />;
  }

  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/shop" element={<ShopPage />} />
      <Route path="/product/:id" element={<ProductDetailPage />} />
      <Route path="/cart" element={<CartPage />} />
      <Route path="/checkout/success" element={<CheckoutSuccessPage />} />
      <Route path="/account" element={<AccountPage />} />
      <Route path="/auth/callback" element={<AuthCallback />} />
    </Routes>
  );
};

// ==================== MAIN APP ====================

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <CartProvider>
          <div className="App bg-[#050505] min-h-screen">
            <div className="grain-overlay" />
            <Navigation />
            <main>
              <AppRouter />
            </main>
            <Footer />
            <NewsletterPopup />
            <Toaster position="bottom-right" theme="dark" />
          </div>
        </CartProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
