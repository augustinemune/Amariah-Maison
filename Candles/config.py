from decouple import config


class Config:
    SECRET_KEY = config("SECRET_KEY")

    SQLALCHEMY_DATABASE_URI = config("DATABASE_URL")

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    RUSTFS_ENDPOINT = config(
        "RUSTFS_ENDPOINT",
        default="http://rustfs:9000",
    )
    RUSTFS_ACCESS_KEY = config("RUSTFS_ACCESS_KEY")
    RUSTFS_SECRET_KEY = config("RUSTFS_SECRET_KEY")
    RUSTFS_BUCKET = config("RUSTFS_BUCKET", default="candles")
    RUSTFS_REGION = config("RUSTFS_REGION", default="us-east-1")
