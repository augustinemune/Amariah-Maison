import os
import uuid
import logging
from functools import wraps
from decimal import Decimal, InvalidOperation

import boto3
from botocore.config import Config as BotoConfig

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
)
from flask_login import (
    current_user,
    login_user,
    logout_user,
    login_required,
)

from config import Config
from extensions import db, migrate, login_manager, csrf
from models import User, Product, ProductImage

logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY must be configured.")

    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        raise RuntimeError("DATABASE_URL must be configured.")

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    # ==========================================================
    # PUBLIC PAGES
    # ==========================================================

    @app.route("/")
    def home():
        products = (
            Product.query.filter_by(is_active=True)
            .order_by(Product.created_at.desc())
            .limit(8)
            .all()
        )
        return render_template("home.html", products=products)

    @app.route("/about")
    def about():
        return render_template("about.html")

    @app.route("/contact", methods=["GET", "POST"])
    def contact():
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip()
            subject = request.form.get("subject", "").strip()
            message = request.form.get("message", "").strip()
            privacy = request.form.get("privacy")

            if not all([name, email, subject, message, privacy]):
                flash("Please complete all required fields.", "error")
                return redirect(url_for("contact"))

            if len(message) < 10:
                flash(
                    "Please provide a little more detail in your message.",
                    "error",
                )
                return redirect(url_for("contact"))

            flash(
                "Your form passed validation. Message delivery is not "
                "configured yet.",
                "success",
            )
            return redirect(url_for("contact"))

        return render_template("contact.html")

    # ==========================================================
    # ADMIN ACCESS CONTROL
    # ==========================================================

    def admin_required(view):
        @wraps(view)
        @login_required
        def wrapped_view(*args, **kwargs):
            if not current_user.is_admin:
                flash(
                    "You are not authorized to access the admin area.",
                    "error",
                )
                return redirect(url_for("home"))
            return view(*args, **kwargs)

        return wrapped_view

    # ==========================================================
    # ADMIN LOGIN AND LOGOUT
    # ==========================================================

    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        if current_user.is_authenticated:
            if current_user.is_admin:
                return redirect(url_for("admin_dashboard"))
            logout_user()

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")

            user = User.query.filter_by(username=username).first()

            if user and user.is_admin and user.check_password(password):
                login_user(user)
                return redirect(url_for("admin_dashboard"))

            flash("Invalid administrator credentials.", "error")

        return render_template("admin/login.html")

    @app.route("/admin/logout", methods=["POST"])
    @login_required
    def admin_logout():
        logout_user()
        flash("You have been signed out.", "success")
        return redirect(url_for("admin_login"))

    # ==========================================================
    # ADMIN DASHBOARD
    # ==========================================================

    @app.route("/admin")
    @admin_required
    def admin_dashboard():
        total_products = Product.query.count()
        active_products = Product.query.filter_by(is_active=True).count()
        out_of_stock = Product.query.filter_by(stock=0).count()

        recent_products = (
            Product.query.order_by(Product.created_at.desc()).limit(5).all()
        )

        return render_template(
            "admin/dashboard.html",
            total_products=total_products,
            active_products=active_products,
            out_of_stock=out_of_stock,
            recent_products=recent_products,
        )

    # ==========================================================
    # PRODUCT INVENTORY
    # ==========================================================

    @app.route("/admin/products")
    @admin_required
    def admin_products():
        products = Product.query.order_by(Product.created_at.desc()).all()
        return render_template(
            "admin/products.html",
            products=products,
        )

    # ==========================================================
    # ADD CANDLE WITH MULTIPLE RUSTFS IMAGES
    # ==========================================================

    @app.route("/admin/products/new", methods=["GET", "POST"])
    @admin_required
    def admin_add_product():
        if request.method == "GET":
            return render_template(
                "admin/product_form.html",
                product=None,
            )

        name = request.form.get("name", "").strip()
        slug = request.form.get("slug", "").strip().lower()
        description = request.form.get("description", "").strip()
        scent = request.form.get("scent", "").strip()
        size = request.form.get("size", "").strip()

        uploaded_images = [
            image
            for image in request.files.getlist("images")
            if image and image.filename and image.filename.strip()
        ]

        # Validate text fields.
        if not name or not slug:
            flash("Product name and slug are required.", "error")
            return redirect(url_for("admin_add_product"))

        if len(name) > 150 or len(slug) > 180:
            flash("Product name or slug is too long.", "error")
            return redirect(url_for("admin_add_product"))

        if Product.query.filter_by(slug=slug).first():
            flash("A product with that slug already exists.", "error")
            return redirect(url_for("admin_add_product"))

        # Validate price and stock.
        try:
            price = Decimal(request.form.get("price", "").strip())
            stock = int(request.form.get("stock", "").strip())

            if not price.is_finite() or price <= 0 or price > Decimal("99999999.99"):
                raise ValueError

            if stock < 0:
                raise ValueError

        except (InvalidOperation, ValueError, TypeError):
            flash(
                "Enter a valid positive price and non-negative stock.",
                "error",
            )
            return redirect(url_for("admin_add_product"))

        # Validate image count, extension, MIME type, and size.
        min_images = 5
        max_images = 10
        max_image_size = 5 * 1024 * 1024

        allowed_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
            ".gif": "image/gif",
        }

        if not min_images <= len(uploaded_images) <= max_images:
            flash(
                f"Upload between {min_images} and {max_images} images.",
                "error",
            )
            return redirect(url_for("admin_add_product"))

        for image in uploaded_images:
            extension = os.path.splitext(image.filename)[1].lower()

            if extension not in allowed_types:
                flash(
                    f"Unsupported image file: {image.filename}",
                    "error",
                )
                return redirect(url_for("admin_add_product"))

            if image.mimetype != allowed_types[extension]:
                flash(
                    f"Invalid image content type: {image.filename}",
                    "error",
                )
                return redirect(url_for("admin_add_product"))

            image.stream.seek(0)
            data = image.stream.read(max_image_size + 1)
            image.stream.seek(0)

            if not data or len(data) > max_image_size:
                flash(
                    f"Each image must be no larger than 5 MB: " f"{image.filename}",
                    "error",
                )
                return redirect(url_for("admin_add_product"))

        try:
            primary_index = int(request.form.get("primary_image_index", "0"))
            if not 0 <= primary_index < len(uploaded_images):
                raise ValueError
        except (ValueError, TypeError):
            flash("Select a valid primary image.", "error")
            return redirect(url_for("admin_add_product"))

        # RustFS configuration.
        endpoint_url = app.config["RUSTFS_ENDPOINT"]
        access_key = app.config["RUSTFS_ACCESS_KEY"]
        secret_key = app.config["RUSTFS_SECRET_KEY"]
        bucket = app.config["RUSTFS_BUCKET"]
        region = app.config["RUSTFS_REGION"]

        if not access_key or not secret_key:
            flash("RustFS credentials are not configured.", "error")
            return redirect(url_for("admin_add_product"))

        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=BotoConfig(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
            ),
        )

        uploaded_keys = []

        try:
            # Create the product without an image= argument.
            product = Product(
                name=name,
                slug=slug,
                description=description,
                price=price,
                stock=stock,
                scent=scent or None,
                size=size or None,
            )

            db.session.add(product)
            db.session.flush()

            # Upload each file and store its RustFS object key.
            for index, image in enumerate(uploaded_images):
                extension = os.path.splitext(image.filename)[1].lower()
                object_key = f"products/{product.id}/{uuid.uuid4().hex}{extension}"

                image.stream.seek(0)

                s3.upload_fileobj(
                    image.stream,
                    bucket,
                    object_key,
                    ExtraArgs={
                        "ContentType": allowed_types[extension],
                    },
                )

                uploaded_keys.append(object_key)

                db.session.add(
                    ProductImage(
                        product=product,
                        object_key=object_key,
                        alt_text=f"{name} - image {index + 1}",
                        is_primary=(index == primary_index),
                        sort_order=index,
                    )
                )

            db.session.commit()

            flash(
                "Product and images uploaded successfully.",
                "success",
            )
            return redirect(url_for("admin_products"))

        except Exception:
            db.session.rollback()

            for object_key in uploaded_keys:
                try:
                    s3.delete_object(
                        Bucket=bucket,
                        Key=object_key,
                    )
                except Exception:
                    app.logger.exception(
                        "Could not clean up RustFS object %s",
                        object_key,
                    )

            app.logger.exception("Product creation or RustFS upload failed.")
            flash(
                "Product creation failed. Check the application logs "
                "and verify the RustFS bucket and credentials.",
                "error",
            )
            return redirect(url_for("admin_add_product"))

    return app


app = create_app()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=3000,
        debug=False,
    )
