import os


class Config:
    # ── Security ──────────────────────────────────────────────────────────
    SECRET_KEY = os.environ.get(
        'SECRET_KEY',
        'SusmithaSecretKey123'
    )

    # ── MySQL (MySQL Workbench) ────────────────────────────────────────────
    # Format: mysql+pymysql://user:password@host:port/dbname
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'mysql+pymysql://root:Susmitha*12@localhost:3306/team_manager'
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ── App Settings ──────────────────────────────────────────────────────
    DEBUG = os.environ.get(
        'FLASK_DEBUG',
        'True'
    ) == 'True'