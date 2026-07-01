import os

os.environ.setdefault('FLASK_TESTING', '1')
os.environ.setdefault('SECRET_KEY', 'test-secret-key')
os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')
