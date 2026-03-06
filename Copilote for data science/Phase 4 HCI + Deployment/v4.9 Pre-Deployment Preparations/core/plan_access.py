# core/plan_access.py — Centralized plan-based feature access control
# All plan gating logic lives here. Import `has_access` in routes.

# ═══════════════════════════════════════════════════════════════════════
# FEATURE MATRIX — which features each plan unlocks
# ═══════════════════════════════════════════════════════════════════════

PLAN_FEATURES = {
    "free": [
        "quick_run",
        "datasets",
        "sessions",
    ],
    "pro": [
        "quick_run",
        "datasets",
        "sessions",
        "workflow",
        "monitoring",
    ],
    "ultra": [
        "quick_run",
        "datasets",
        "sessions",
        "workflow",
        "monitoring",
        "advanced_agent",
    ],
}

# ═══════════════════════════════════════════════════════════════════════
# UPLOAD LIMITS (bytes) per plan
# ═══════════════════════════════════════════════════════════════════════

PLAN_UPLOAD_LIMITS = {
    "free":  25 * 1024 * 1024,       # 25 MB
    "pro":   500 * 1024 * 1024,      # 500 MB
    "ultra": 2 * 1024 * 1024 * 1024, # 2 GB (system max)
}

# ═══════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════

def has_access(user, feature):
    """Check if user's plan grants access to a feature."""
    return feature in PLAN_FEATURES.get(user.plan, [])


def get_upload_limit(plan):
    """Return max upload size in bytes for the given plan."""
    return PLAN_UPLOAD_LIMITS.get(plan, PLAN_UPLOAD_LIMITS["free"])


# ═══════════════════════════════════════════════════════════════════════
# PLAN LIMITS — exposed to monitoring dashboard
# ═══════════════════════════════════════════════════════════════════════

PLAN_LIMITS = {
    "free": {
        "dataset_size_limit": "25 MB",
        "credits_limit": "100K",
        "workflow_enabled": False,
        "monitoring_enabled": False,
        "max_power_toggle": False,
    },
    "pro": {
        "dataset_size_limit": "500 MB",
        "credits_limit": "1M",
        "workflow_enabled": True,
        "monitoring_enabled": True,
        "max_power_toggle": True,
    },
    "ultra": {
        "dataset_size_limit": "2 GB",
        "credits_limit": "Unlimited",
        "workflow_enabled": True,
        "monitoring_enabled": True,
        "max_power_toggle": True,
    },
}


def get_plan_limits(plan):
    """Return the limits dict for a given plan."""
    return PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])
