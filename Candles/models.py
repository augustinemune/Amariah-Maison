import uuid
from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db, login_manager


def utc_now():
    return datetime.now(timezone.utc)


def generate_uuid():
    return uuid.uuid4()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(
        db.Uuid(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username}>"


@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, uuid.UUID(user_id))
    except (ValueError, TypeError, AttributeError):
        return None


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(
        db.Uuid(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )
    name = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(180), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    price = db.Column(db.Numeric(10, 2), nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)
    scent = db.Column(db.String(100), nullable=True)
    size = db.Column(db.String(80), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    images = db.relationship(
        "ProductImage",
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductImage.sort_order",
    )

    @property
    def primary_image(self):
        return next(
            (image for image in self.images if image.is_primary),
            self.images[0] if self.images else None,
        )

    def __repr__(self):
        return f"<Product {self.name}>"


class ProductImage(db.Model):
    __tablename__ = "product_images"

    id = db.Column(
        db.Uuid(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )
    product_id = db.Column(
        db.Uuid(as_uuid=True),
        db.ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Object key inside the RustFS bucket, not the file itself.
    object_key = db.Column(db.String(1024), nullable=False, unique=True)

    alt_text = db.Column(db.String(255), nullable=False, default="")
    is_primary = db.Column(db.Boolean, nullable=False, default=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    product = db.relationship("Product", back_populates="images")

    def __repr__(self):
        return f"<ProductImage {self.object_key}>"


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(
        db.Uuid(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )
    order_number = db.Column(
        db.String(40),
        unique=True,
        nullable=False,
    )
    customer_name = db.Column(db.String(150), nullable=False)
    customer_email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    delivery_address = db.Column(db.Text, nullable=False)

    total = db.Column(db.Numeric(12, 2), nullable=False)
    status = db.Column(
        db.String(30),
        default="pending",
        nullable=False,
    )
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    items = db.relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Order {self.order_number}>"


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(
        db.Uuid(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )
    order_id = db.Column(
        db.Uuid(as_uuid=True),
        db.ForeignKey("orders.id"),
        nullable=False,
    )
    product_id = db.Column(
        db.Uuid(as_uuid=True),
        db.ForeignKey("products.id"),
        nullable=True,
    )

    # Preserve product details at the time of purchase.
    product_name = db.Column(db.String(150), nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)

    order = db.relationship("Order", back_populates="items")
    product = db.relationship("Product")

    def __repr__(self):
        return f"<OrderItem {self.product_name}>"
