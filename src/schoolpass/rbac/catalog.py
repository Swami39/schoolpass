SYSTEM_ROLES = (
    "platform_super_admin",
    "platform_support",
    "platform_billing",
    "school_admin",
    "school_finance",
    "teacher",
    "bus_attendant",
    "parent",
)

PERMISSIONS: dict[str, str] = {
    "tenant:read": "Read tenant profile",
    "staff:read": "Read staff profiles",
    "staff:write": "Write staff profiles",
    "audit:read": "Read audit logs",
    "membership:read": "Read memberships",
    "membership:write": "Write memberships",
}

ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "platform_super_admin": tuple(PERMISSIONS.keys()),
    "platform_support": ("tenant:read", "staff:read", "audit:read", "membership:read"),
    "platform_billing": ("tenant:read",),
    "school_admin": (
        "tenant:read",
        "staff:read",
        "staff:write",
        "audit:read",
        "membership:read",
        "membership:write",
    ),
    "school_finance": ("tenant:read", "membership:read"),
    "teacher": ("tenant:read", "staff:read"),
    "bus_attendant": ("tenant:read",),
    "parent": ("tenant:read",),
}

PLATFORM_ROLES = {"platform_super_admin", "platform_support", "platform_billing"}
MFA_REQUIRED_ROLES = {"platform_super_admin", "platform_support", "platform_billing", "school_admin"}
