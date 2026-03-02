# routes/__init__.py — Blueprint registration
from routes.auth_routes import auth_bp
from routes.dataset_routes import dataset_bp
from routes.normal_routes import normal_bp
from routes.pro_routes import pro_bp
from routes.profile_routes import profile_bp

ALL_BLUEPRINTS = [auth_bp, dataset_bp, normal_bp, pro_bp, profile_bp]
