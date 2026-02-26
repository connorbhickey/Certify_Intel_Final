"""
Certify Intel - Extended Models and Features
User Authentication, Win/Loss Database, SimilarWeb, Social Media, Caching
"""
import os
import hashlib
import secrets
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from functools import lru_cache
import json

logger = logging.getLogger(__name__)

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

try:
    from jose import jwt
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False

# Use hashlib for password hashing (Python 3.14 compatible)
# bcrypt/passlib has compatibility issues with Python 3.14
AUTH_AVAILABLE = True



# ============== User Authentication ==============

from database import User, RefreshToken, SessionLocal
from sqlalchemy.orm import Session

# JWT settings
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15  # 15 minutes (short-lived, use refresh tokens)
REFRESH_TOKEN_EXPIRE_DAYS = 7  # 7 days


class AuthManager:
    """Handles user authentication with Database Persistence."""
    
    def __init__(self):
        pass
    
    # Default credentials for desktop app / fresh installs
    DEFAULT_ADMIN_EMAIL = "admin@certifyhealth.com"
    DEFAULT_ADMIN_PASSWORD = "CertifyIntel2026!"

    def ensure_default_admin(self, db: Session):
        """Create default admin user if not exists.

        Reads ADMIN_EMAIL and ADMIN_PASSWORD from environment variables.
        If not set, uses built-in defaults so the desktop app works out of the box.
        """
        try:
            admin_email = os.getenv("ADMIN_EMAIL") or self.DEFAULT_ADMIN_EMAIL
            admin_password = os.getenv("ADMIN_PASSWORD") or self.DEFAULT_ADMIN_PASSWORD

            existing = db.query(User).filter(User.email == admin_email).first()
            if not existing:
                # Check if ANY user exists (maybe admin email was different)
                any_user = db.query(User).first()
                if any_user:
                    logger.info("Users exist but no match for admin email. Skipping admin creation.")
                    return
                logger.info(f"Creating default admin: {admin_email}")
                self.create_user(
                    db,
                    email=admin_email,
                    password=admin_password,
                    full_name="System Admin",
                    role="admin"
                )
                if not os.getenv("ADMIN_PASSWORD"):
                    logger.info(
                        "Admin account created with default credentials. "
                        f"Email: {admin_email} | Password: {self.DEFAULT_ADMIN_PASSWORD} — "
                        "Change this after first login in Settings."
                    )
                else:
                    logger.info("Admin account created successfully. You can now log in.")
            else:
                # Admin exists — ensure the password matches what's configured.
                # This handles shipped databases where the admin was created
                # with a different password during development.
                if not self.verify_password(admin_password, existing.hashed_password):
                    logger.info("Admin password mismatch — resetting to configured password.")
                    existing.hashed_password = self.hash_password(admin_password)
                    db.commit()
        except Exception as e:
            logger.error(f"Error ensuring default admin: {e}")
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against hash. Supports PBKDF2 ($ and : separators) and legacy SHA256."""
        # PBKDF2 format: salt_hex$hash_hex (current) or salt_hex:hash_hex (older builds)
        for sep in ("$", ":"):
            if sep in hashed_password:
                try:
                    salt_hex, stored_hash = hashed_password.split(sep, 1)
                    salt = bytes.fromhex(salt_hex)
                    computed = hashlib.pbkdf2_hmac(
                        "sha256", plain_password.encode(), salt, 600_000
                    ).hex()
                    return secrets.compare_digest(computed, stored_hash)
                except (ValueError, TypeError):
                    return False
        # Legacy SHA256 format (backward compatibility)
        return secrets.compare_digest(
            self._hash_password_legacy(plain_password), hashed_password
        )

    def _hash_password_legacy(self, password: str) -> str:
        """Legacy SHA256 hash for backward compatibility only."""
        salted = f"{SECRET_KEY}{password}"
        return hashlib.sha256(salted.encode()).hexdigest()

    def hash_password(self, password: str) -> str:
        """Hash a password using PBKDF2-HMAC-SHA256 with per-user random salt."""
        salt = secrets.token_bytes(32)
        pw_hash = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt, 600_000
        ).hex()
        return f"{salt.hex()}${pw_hash}"
    
    def create_user(self, db: Session, email: str, password: str, full_name: str = "", role: str = "viewer") -> User:
        """Create a new user in DB."""
        # hashed_password = self.hash_password(password)
        # user = User(email=email, hashed_password=hashed_password, full_name=full_name, role=role)
        # Check if exists
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            return existing
            
        hashed = self.hash_password(password)
        new_user = User(
            email=email,
            hashed_password=hashed,
            full_name=full_name,
            role=role,
            is_active=True
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user
    
    def authenticate_user(self, db: Session, email: str, password: str) -> Optional[User]:
        """Authenticate user credentials against DB."""
        user = db.query(User).filter(User.email == email).first()
        if not user or not user.is_active:
            return None
        if not self.verify_password(password, user.hashed_password):
            return None
        return user
    
    def create_access_token(self, data: dict, expires_delta: timedelta = None) -> str:
        """Create JWT access token."""
        to_encode = data.copy()
        expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
        to_encode.update({"exp": expire})
        
        if AUTH_AVAILABLE:
            return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        else:
            # Simple token for demo
            return hashlib.sha256(json.dumps(to_encode).encode()).hexdigest()
    
    def verify_token(self, token: str) -> Optional[dict]:
        """Verify JWT token."""
        try:
            if AUTH_AVAILABLE:
                payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                return payload
        except (jwt.JWTError, jwt.ExpiredSignatureError, Exception) as e:
            logger.debug(f"Token verification failed: {e}")
        return None

    def create_refresh_token(self, db: Session, user_id: int) -> str:
        """Create and store a refresh token for the given user."""
        import uuid
        token_value = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

        refresh_token = RefreshToken(
            token=token_value,
            user_id=user_id,
            expires_at=expires_at,
            revoked=False
        )
        db.add(refresh_token)
        db.commit()
        return token_value

    def validate_refresh_token(self, db: Session, token_value: str) -> Optional[RefreshToken]:
        """Validate a refresh token. Returns the token record if valid, None otherwise."""
        token_record = db.query(RefreshToken).filter(
            RefreshToken.token == token_value,
            RefreshToken.revoked == False  # noqa: E712
        ).first()

        if not token_record:
            return None

        if token_record.expires_at < datetime.utcnow():
            # Expired - revoke it
            token_record.revoked = True
            db.commit()
            return None

        return token_record

    def revoke_refresh_token(self, db: Session, token_value: str) -> bool:
        """Revoke a refresh token. Returns True if found and revoked."""
        token_record = db.query(RefreshToken).filter(
            RefreshToken.token == token_value
        ).first()

        if not token_record:
            return False

        token_record.revoked = True
        db.commit()
        return True

    def revoke_all_user_tokens(self, db: Session, user_id: int) -> int:
        """Revoke all refresh tokens for a user. Returns count revoked."""
        count = db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked == False  # noqa: E712
        ).update({"revoked": True})
        db.commit()
        return count

    def cleanup_expired_tokens(self, db: Session) -> int:
        """Remove expired refresh tokens older than 30 days. Returns count deleted."""
        cutoff = datetime.utcnow() - timedelta(days=30)
        count = db.query(RefreshToken).filter(
            RefreshToken.expires_at < cutoff
        ).delete()
        db.commit()
        return count


# ============== Win/Loss Database ==============

class WinLossRecord:
    """Record of a competitive deal."""
    def __init__(
        self,
        id: int,
        competitor_id: Optional[int],
        competitor_name: str,
        outcome: str,  # "win" or "loss"
        deal_value: Optional[float] = None,
        deal_date: datetime = None,
        customer_name: Optional[str] = None,
        customer_size: Optional[str] = None,
        loss_reason: Optional[str] = None,
        win_factor: Optional[str] = None,
        sales_rep: Optional[str] = None,
        notes: Optional[str] = None
    ):
        self.id = id
        self.competitor_id = competitor_id
        self.competitor_name = competitor_name
        self.outcome = outcome
        self.deal_value = deal_value
        self.deal_date = deal_date or datetime.utcnow()
        self.customer_name = customer_name
        self.customer_size = customer_size
        self.loss_reason = loss_reason
        self.win_factor = win_factor
        self.sales_rep = sales_rep
        self.notes = notes


class WinLossTracker:
    """Tracks competitive win/loss data."""
    
    def __init__(self):
        self.records: List[WinLossRecord] = []
        self._load_sample_data()
    
    def _load_sample_data(self):
        """Load sample win/loss data."""
        sample = [
            WinLossRecord(1, 1, "Phreesia", "loss", 50000, 
                         loss_reason="Feature gap - lacked telehealth",
                         customer_size="Large (50+)"),
            WinLossRecord(2, 2, "Clearwave", "win", 35000,
                         win_factor="Faster implementation",
                         customer_size="Medium (15-50)"),
            WinLossRecord(3, 1, "Phreesia", "win", 45000,
                         win_factor="Better EHR integration",
                         customer_size="Medium (15-50)"),
            WinLossRecord(4, 5, "Kareo", "loss", 15000,
                         loss_reason="Price too high",
                         customer_size="Small (1-15)"),
            WinLossRecord(5, 3, "Epion Health", "win", 60000,
                         win_factor="Customer support",
                         customer_size="Large (50+)"),
        ]
        self.records = sample
    
    def add_record(self, record: WinLossRecord):
        """Add a new win/loss record."""
        record.id = len(self.records) + 1
        self.records.append(record)
    
    def get_records(self, competitor_name: Optional[str] = None, outcome: Optional[str] = None) -> List[WinLossRecord]:
        """Get filtered records."""
        result = self.records
        if competitor_name:
            result = [r for r in result if r.competitor_name.lower() == competitor_name.lower()]
        if outcome:
            result = [r for r in result if r.outcome == outcome]
        return result
    
    def get_stats(self) -> Dict[str, Any]:
        """Get win/loss statistics."""
        wins = [r for r in self.records if r.outcome == "win"]
        losses = [r for r in self.records if r.outcome == "loss"]
        
        win_rate = len(wins) / len(self.records) * 100 if self.records else 0
        
        # By competitor
        by_competitor = {}
        for r in self.records:
            if r.competitor_name not in by_competitor:
                by_competitor[r.competitor_name] = {"wins": 0, "losses": 0}
            by_competitor[r.competitor_name][f"{r.outcome}s" if r.outcome == "win" else "losses"] += 1
        
        # Calculate win rates per competitor
        for comp, data in by_competitor.items():
            total = data["wins"] + data["losses"]
            data["win_rate"] = round(data["wins"] / total * 100, 1) if total > 0 else 0
        
        # Common loss reasons
        loss_reasons = {}
        for r in losses:
            if r.loss_reason:
                loss_reasons[r.loss_reason] = loss_reasons.get(r.loss_reason, 0) + 1
        
        # Common win factors
        win_factors = {}
        for r in wins:
            if r.win_factor:
                win_factors[r.win_factor] = win_factors.get(r.win_factor, 0) + 1
        
        return {
            "total_deals": len(self.records),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(win_rate, 1),
            "total_value_won": sum(r.deal_value or 0 for r in wins),
            "total_value_lost": sum(r.deal_value or 0 for r in losses),
            "by_competitor": by_competitor,
            "top_loss_reasons": dict(sorted(loss_reasons.items(), key=lambda x: -x[1])[:5]),
            "top_win_factors": dict(sorted(win_factors.items(), key=lambda x: -x[1])[:5]),
        }


# ============== SimilarWeb Integration ==============

class SimilarWebData:
    """SimilarWeb traffic data."""
    def __init__(
        self,
        domain: str,
        total_visits: int = 0,
        avg_visit_duration: str = "0:00",
        pages_per_visit: float = 0,
        bounce_rate: float = 0,
        traffic_sources: Dict[str, float] = None,
        top_countries: Dict[str, float] = None,
        scraped_at: datetime = None
    ):
        self.domain = domain
        self.total_visits = total_visits
        self.avg_visit_duration = avg_visit_duration
        self.pages_per_visit = pages_per_visit
        self.bounce_rate = bounce_rate
        self.traffic_sources = traffic_sources or {}
        self.top_countries = top_countries or {}
        self.scraped_at = scraped_at or datetime.utcnow()


class SimilarWebScraper:
    """Fetches traffic data from SimilarWeb."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("SIMILARWEB_API_KEY")
    
    async def get_traffic_data(self, domain: str) -> SimilarWebData:
        """Get traffic data for a domain. Returns unavailable data when no real API key is configured."""
        # SimilarWeb requires paid API access - return empty data instead of fabricated numbers
        clean_domain = domain.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
        return SimilarWebData(domain=clean_domain, total_visits=0)


# ============== Social Media Monitoring ==============

class SocialPost:
    """Social media post/mention."""
    def __init__(
        self,
        platform: str,  # twitter, linkedin, facebook
        content: str,
        url: str,
        author: Optional[str] = None,
        posted_at: datetime = None,
        engagement: int = 0,
        sentiment: Optional[str] = None  # positive, negative, neutral
    ):
        self.platform = platform
        self.content = content
        self.url = url
        self.author = author
        self.posted_at = posted_at or datetime.utcnow()
        self.engagement = engagement
        self.sentiment = sentiment


class SocialMediaMonitor:
    """Monitors social media for competitor mentions."""
    
    def __init__(self):
        self.twitter_api_key = os.getenv("TWITTER_API_KEY")
        self.linkedin_api_key = os.getenv("LINKEDIN_API_KEY")
    
    async def search_mentions(self, company_name: str, days: int = 7) -> List[SocialPost]:
        """Search for company mentions across social platforms.
        Returns empty list when no real API keys are configured."""
        # Requires API access to social platforms (Twitter, LinkedIn, etc.)
        # Return empty list instead of fabricated mock posts
        return []
    
    def analyze_sentiment(self, posts: List[SocialPost]) -> Dict[str, Any]:
        """Analyze sentiment across posts."""
        if not posts:
            return {"total": 0, "positive": 0, "negative": 0, "neutral": 0}
        
        sentiments = {"positive": 0, "negative": 0, "neutral": 0}
        for post in posts:
            if post.sentiment:
                sentiments[post.sentiment] += 1
        
        total = len(posts)
        return {
            "total": total,
            "positive": sentiments["positive"],
            "negative": sentiments["negative"],
            "neutral": sentiments["neutral"],
            "sentiment_score": round((sentiments["positive"] - sentiments["negative"]) / total * 100, 1)
        }


# ============== API Rate Limiting & Caching ==============

class RateLimiter:
    """Simple in-memory rate limiter."""
    
    def __init__(self, requests_per_minute: int = 60):
        self.limit = requests_per_minute
        self.requests: Dict[str, List[datetime]] = {}
    
    def is_allowed(self, client_id: str) -> bool:
        """Check if request is allowed."""
        now = datetime.utcnow()
        minute_ago = now - timedelta(minutes=1)
        
        # Clean old requests
        if client_id in self.requests:
            self.requests[client_id] = [
                t for t in self.requests[client_id] 
                if t > minute_ago
            ]
        else:
            self.requests[client_id] = []
        
        # Check limit
        if len(self.requests[client_id]) >= self.limit:
            return False
        
        self.requests[client_id].append(now)
        return True
    
    def get_remaining(self, client_id: str) -> int:
        """Get remaining requests for this minute."""
        now = datetime.utcnow()
        minute_ago = now - timedelta(minutes=1)
        
        if client_id not in self.requests:
            return self.limit
        
        recent = [t for t in self.requests[client_id] if t > minute_ago]
        return max(0, self.limit - len(recent))


class CacheManager:
    """Manages API response caching."""
    
    def __init__(self, ttl_seconds: int = 300):
        self.ttl = ttl_seconds
        self.cache: Dict[str, tuple] = {}  # key -> (value, expiry)
        self.redis_client = None
        
        if REDIS_AVAILABLE and os.getenv("TESTING") != "true":
            try:
                self.redis_client = redis.Redis(
                    host=os.getenv("REDIS_HOST", "localhost"),
                    port=int(os.getenv("REDIS_PORT", 6379)),
                    decode_responses=True,
                    socket_connect_timeout=2,  # Don't hang if Redis is down
                    socket_timeout=2
                )
                self.redis_client.ping()
            except (ConnectionError, Exception) as e:
                logger.debug(f"Redis connection failed, using in-memory cache: {e}")
                self.redis_client = None

    def get(self, key: str) -> Optional[Any]:
        """Get cached value."""
        if self.redis_client:
            try:
                value = self.redis_client.get(key)
                return json.loads(value) if value else None
            except (ConnectionError, json.JSONDecodeError, Exception) as e:
                logger.debug(f"Redis get failed: {e}")

        # Fallback to in-memory
        if key in self.cache:
            value, expiry = self.cache[key]
            if datetime.utcnow() < expiry:
                return value
            del self.cache[key]
        return None

    def set(self, key: str, value: Any, ttl: int = None):
        """Set cached value."""
        ttl = ttl or self.ttl

        if self.redis_client:
            try:
                self.redis_client.setex(key, ttl, json.dumps(value))
                return
            except (ConnectionError, TypeError, Exception) as e:
                logger.debug(f"Redis set failed: {e}")

        # Fallback to in-memory
        expiry = datetime.utcnow() + timedelta(seconds=ttl)
        self.cache[key] = (value, expiry)

    def invalidate(self, key: str):
        """Invalidate cached value."""
        if self.redis_client:
            try:
                self.redis_client.delete(key)
            except (ConnectionError, Exception) as e:
                logger.debug(f"Redis invalidate failed: {e}")

        if key in self.cache:
            del self.cache[key]

    def clear_all(self):
        """Clear all cached values."""
        if self.redis_client:
            try:
                self.redis_client.flushdb()
            except (ConnectionError, Exception) as e:
                logger.debug(f"Redis flush failed: {e}")
        self.cache.clear()


# Decorator for caching function results
def cached(ttl_seconds: int = 300):
    """Decorator for caching function results."""
    cache_manager = CacheManager(ttl_seconds)
    
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"
            
            # Try to get from cache
            cached_value = cache_manager.get(key)
            if cached_value is not None:
                return cached_value
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Cache result
            cache_manager.set(key, result)
            
            return result
        return wrapper
    return decorator


# ============== Singleton Instances ==============

auth_manager = AuthManager()
win_loss_tracker = WinLossTracker()
rate_limiter = RateLimiter()
cache_manager = CacheManager()
similarweb_scraper = SimilarWebScraper()
social_monitor = SocialMediaMonitor()


if __name__ == "__main__":
    # Test
    print("Win/Loss Stats:")
    print(json.dumps(win_loss_tracker.get_stats(), indent=2))

# ============== Workflow Automation ==============

from database import Competitor
from sqlalchemy.orm import Session

KNOWN_TICKERS = {
    "phreesia": {"symbol": "PHR", "exchange": "NYSE", "name": "Phreesia Inc"},
    "health catalyst": {"symbol": "HCAT", "exchange": "NASDAQ", "name": "Health Catalyst Inc"},
    "veeva": {"symbol": "VEEV", "exchange": "NYSE", "name": "Veeva Systems Inc"},
    "teladoc": {"symbol": "TDOC", "exchange": "NYSE", "name": "Teladoc Health Inc"},
    "doximity": {"symbol": "DOCS", "exchange": "NYSE", "name": "Doximity Inc"},
    "hims & hers": {"symbol": "HIMS", "exchange": "NYSE", "name": "Hims & Hers Health Inc"},
    "definitive healthcare": {"symbol": "DH", "exchange": "NASDAQ", "name": "Definitive Healthcare Corp"},
    "carecloud": {"symbol": "CCLD", "exchange": "NASDAQ", "name": "CareCloud Inc"},
}

class ClassificationWorkflow:
    """Automated workflow for classifying competitors."""
    
    def __init__(self, db: Session):
        self.db = db
        
    def run_classification_pipeline(self):
        """Run the full classification pipeline."""
        print("Starting automated classification pipeline...")
        try:
            competitors = self.db.query(Competitor).filter(Competitor.is_deleted == False).all()
            updates_count = 0
            for comp in competitors:
                comp_name_lower = comp.name.lower()
                if comp_name_lower in KNOWN_TICKERS:
                    info = KNOWN_TICKERS[comp_name_lower]
                    if not comp.is_public or comp.ticker_symbol != info["symbol"]:
                        print(f"  [AUTO-CLASSIFY] Identifying {comp.name} as PUBLIC ({info['symbol']})")
                        comp.is_public = True
                        comp.ticker_symbol = info["symbol"]
                        comp.stock_exchange = info["exchange"]
                        updates_count += 1
            if updates_count > 0:
                self.db.commit()
            print(f"Classification validation complete. {updates_count} records updated/verified.")
        except Exception as e:
            print(f"Error in classification pipeline: {e}")
        finally:
            self.db.close()
