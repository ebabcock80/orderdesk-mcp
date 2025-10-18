"""WebUI routes for OrderDesk MCP Server admin interface."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from mcp_server.config import settings
from mcp_server.models.database import get_db
from mcp_server.services.store import StoreService
from mcp_server.services.user import UserService
from mcp_server.services.rate_limit import RateLimitService
from mcp_server.email import EmailService
from mcp_server.email.providers import ConsoleEmailProvider, SMTPEmailProvider
from mcp_server.email.magic_link import MagicLinkService
from mcp_server.utils.master_key import generate_master_key
from mcp_server.auth.crypto import hash_master_key
from mcp_server.utils.logging import logger
from mcp_server.webui.auth import (
    auth_manager,
    create_session_cookie,
    generate_csrf_token,
    get_current_user,
)

router = APIRouter(prefix="/webui", tags=["webui"])

# Lazy-load templates to avoid import-time issues
_templates = None


def get_templates():
    """Get or create Jinja2 templates instance."""
    global _templates
    if _templates is None:
        _templates = Jinja2Templates(directory="mcp_server/templates")
    return _templates


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Display login page."""
    csrf_token = generate_csrf_token()

    return get_templates().TemplateResponse(
        "login.html",
        {
            "request": request,
            "csrf_token": csrf_token,
            "error": None,
            "signup_enabled": settings.enable_public_signup,
        },
    )


@router.post("/login")
async def login(
    request: Request,
    master_key: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Authenticate user with master key.

    Args:
        request: FastAPI request
        master_key: Master key from form
        csrf_token: CSRF token from form
        db: Database session

    Returns:
        Redirect to dashboard on success, login page with error on failure
    """
    # Authenticate
    success, tenant_id = await auth_manager.authenticate_master_key(master_key, db)

    if not success or tenant_id is None:
        # Authentication failed
        new_csrf = generate_csrf_token()
        return get_templates().TemplateResponse(
            "login.html",
            {
                "request": request,
                "csrf_token": new_csrf,
                "error": "Invalid master key. Please try again.",
            },
            status_code=401,
        )

    # Create session token
    session_token = auth_manager.create_session_token(tenant_id)

    # Update last_login timestamp (Phase 6)
    user_service = UserService(db)
    await user_service.update_last_login(tenant_id)

    # Create response with session cookie
    response = RedirectResponse(url="/webui/dashboard", status_code=303)
    cookie_config = create_session_cookie(session_token)
    response.set_cookie(**cookie_config)

    logger.info("WebUI login successful", tenant_id=tenant_id)

    return response


@router.get("/logout")
async def logout():
    """Logout user by clearing session cookie."""
    response = RedirectResponse(url="/webui/login", status_code=303)
    response.delete_cookie("session")
    return response


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Display admin dashboard.

    Args:
        request: FastAPI request
        user: Current authenticated user
        db: Database session

    Returns:
        Dashboard HTML page
    """
    tenant_id = user["tenant_id"]

    # Get stores for this tenant
    store_service = StoreService(db)
    stores = await store_service.list_stores(tenant_id)

    # Get recent activity (audit logs)
    # TODO: Implement when audit log service is ready

    return get_templates().TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "store_count": len(stores),
            "stores": stores[:5],  # Show first 5
            "csrf_token": generate_csrf_token(),
        },
    )


@router.get("/stores", response_class=HTMLResponse)
async def list_stores(
    request: Request,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Display list of registered stores.

    Args:
        request: FastAPI request
        user: Current authenticated user
        db: Database session

    Returns:
        Stores list HTML page
    """
    tenant_id = user["tenant_id"]

    # Get all stores
    store_service = StoreService(db)
    stores = await store_service.list_stores(tenant_id)

    return get_templates().TemplateResponse(
        "stores/list.html",
        {
            "request": request,
            "user": user,
            "stores": stores,
            "csrf_token": generate_csrf_token(),
        },
    )


@router.get("/stores/add", response_class=HTMLResponse)
async def add_store_form(
    request: Request,
    user: dict = Depends(get_current_user),
):
    """Display add store form."""
    return get_templates().TemplateResponse(
        "stores/add.html",
        {
            "request": request,
            "user": user,
            "csrf_token": generate_csrf_token(),
            "error": None,
        },
    )


@router.post("/stores/add")
async def add_store(
    request: Request,
    store_name: str = Form(...),
    store_id: str = Form(...),
    api_key: str = Form(...),
    label: str = Form(None),
    csrf_token: str = Form(...),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Add new store registration.

    Args:
        request: FastAPI request
        store_name: Store name
        store_id: OrderDesk store ID
        api_key: OrderDesk API key
        label: Optional label
        csrf_token: CSRF token
        user: Current authenticated user
        db: Database session

    Returns:
        Redirect to stores list on success
    """
    tenant_id = str(user["tenant_id"])
    store_service = StoreService(db)

    try:
        # Register store
        await store_service.register_store(
            tenant_id=tenant_id,
            store_id=store_id,
            api_key=api_key,
            store_name=store_name,
            label=label,
        )

        logger.info(
            "Store registered via WebUI",
            tenant_id=tenant_id,
            store_name=store_name,
        )

        # Redirect to stores list
        return RedirectResponse(url="/webui/stores", status_code=303)

    except Exception as e:
        logger.error("Failed to register store via WebUI", error=str(e))

        return get_templates().TemplateResponse(
            "stores/add.html",
            {
                "request": request,
                "user": user,
                "csrf_token": generate_csrf_token(),
                "error": f"Failed to register store: {str(e)}",
                "store_name": store_name,
                "store_id": store_id,
                "label": label,
            },
            status_code=400,
        )


@router.post("/stores/{store_id}/delete")
async def delete_store(
    store_id: int,
    csrf_token: str = Form(...),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete store registration.

    Args:
        store_id: Store database ID
        csrf_token: CSRF token
        user: Current authenticated user
        db: Database session

    Returns:
        Redirect to stores list
    """
    tenant_id = str(user["tenant_id"])
    store_service = StoreService(db)

    try:
        await store_service.delete_store(tenant_id, str(store_id))
        logger.info("Store deleted via WebUI", tenant_id=tenant_id, store_id=store_id)
    except Exception as e:
        logger.error("Failed to delete store via WebUI", error=str(e))
        # Still redirect, but could add flash message

    return RedirectResponse(url="/webui/stores", status_code=303)


@router.get("/stores/{store_id}", response_class=HTMLResponse)
async def store_details(
    request: Request,
    store_id: int,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Display store details.

    Args:
        request: FastAPI request
        store_id: Store database ID
        user: Current authenticated user
        db: Database session

    Returns:
        Store details HTML page
    """
    tenant_id = str(user["tenant_id"])
    store_service = StoreService(db)

    # Get store
    store = await store_service.get_store(tenant_id, str(store_id))
    if not store:
        # Store not found - redirect to list
        return RedirectResponse(url="/webui/stores", status_code=303)

    return get_templates().TemplateResponse(
        "stores/details.html",
        {
            "request": request,
            "user": user,
            "store": store,
            "csrf_token": generate_csrf_token(),
        },
    )


@router.get("/stores/{store_id}/edit", response_class=HTMLResponse)
async def edit_store_form(
    request: Request,
    store_id: int,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Display edit store form."""
    tenant_id = str(user["tenant_id"])
    store_service = StoreService(db)

    # Get store
    store = await store_service.get_store(tenant_id, str(store_id))
    if not store:
        return RedirectResponse(url="/webui/stores", status_code=303)

    return get_templates().TemplateResponse(
        "stores/edit.html",
        {
            "request": request,
            "user": user,
            "store": store,
            "csrf_token": generate_csrf_token(),
            "error": None,
        },
    )


@router.post("/stores/{store_id}/edit")
async def edit_store(
    request: Request,
    store_id: int,
    store_name: str = Form(...),
    label: str = Form(None),
    store_id_new: str = Form(None, alias="store_id"),
    api_key: str = Form(None, alias="api_key"),
    csrf_token: str = Form(...),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update store registration.

    Args:
        request: FastAPI request
        store_id: Store database ID (from URL)
        store_name: Updated store name
        label: Updated label
        store_id_new: New OrderDesk store ID (optional)
        api_key: New API key (optional)
        csrf_token: CSRF token
        user: Current authenticated user
        db: Database session

    Returns:
        Redirect to store details on success
    """
    tenant_id = user["tenant_id"]
    store_service = StoreService(db)

    # Get existing store
    store = await store_service.get_store(tenant_id, store_id)
    if not store:
        return RedirectResponse(url="/webui/stores", status_code=303)

    try:
        # Update store
        # Note: Currently update_store doesn't exist in StoreService
        # For now, we'll update the database directly

        # Update basic info
        store.store_name = store_name
        store.label = label if label else None

        # Update credentials if provided
        if store_id_new and store_id_new.strip():
            store.store_id = store_id_new

        if api_key and api_key.strip():
            # Re-encrypt API key
            from mcp_server.auth.crypto import get_crypto_manager
            from mcp_server.models.database import Tenant

            tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
            if tenant:
                crypto = get_crypto_manager()
                ciphertext, tag, nonce = crypto.encrypt_api_key(
                    api_key, tenant.master_key_hash, str(tenant.salt)
                )
                store.api_key_ciphertext = ciphertext
                store.api_key_tag = tag
                store.api_key_nonce = nonce

        db.commit()

        logger.info(
            "Store updated via WebUI",
            tenant_id=tenant_id,
            store_id=store_id,
            store_name=store_name,
        )

        # Redirect to store details
        return RedirectResponse(url=f"/webui/stores/{store_id}", status_code=303)

    except Exception as e:
        logger.error("Failed to update store via WebUI", error=str(e))
        db.rollback()

        return get_templates().TemplateResponse(
            "stores/edit.html",
            {
                "request": request,
                "user": user,
                "store": store,
                "csrf_token": generate_csrf_token(),
                "error": f"Failed to update store: {str(e)}",
                "store_name": store_name,
                "label": label,
            },
            status_code=400,
        )


@router.post("/stores/{store_id}/test")
async def test_store_connection(
    store_id: int,
    csrf_token: str = Form(...),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Test store connection to OrderDesk API.

    Args:
        store_id: Store database ID
        csrf_token: CSRF token
        user: Current authenticated user
        db: Database session

    Returns:
        Redirect to store details with result (would show in flash message)
    """
    tenant_id = user["tenant_id"]
    store_service = StoreService(db)

    try:
        # Test the connection
        result = await store_service.test_store_credentials(tenant_id, store_id)

        if result:
            logger.info(
                "Store connection test successful",
                tenant_id=tenant_id,
                store_id=store_id,
            )
        else:
            logger.warning(
                "Store connection test failed",
                tenant_id=tenant_id,
                store_id=store_id,
            )

    except Exception as e:
        logger.error("Store connection test error", error=str(e))

    # Redirect back to store details
    # TODO: Add flash message to show test result
    return RedirectResponse(url=f"/webui/stores/{store_id}", status_code=303)


@router.get("/console", response_class=HTMLResponse)
async def api_console(
    request: Request,
    user: dict = Depends(get_current_user),
):
    """
    Display API test console.

    Args:
        request: FastAPI request
        user: Current authenticated user

    Returns:
        API console HTML page
    """
    import json

    # Comprehensive tool definitions
    tools_dict = {
        "tenant.use_master_key": {
            "name": "tenant.use_master_key",
            "description": "Authenticate with master key",
            "params": [
                {
                    "name": "master_key",
                    "type": "password",
                    "required": True,
                    "placeholder": "Your master key",
                }
            ],
        },
        "stores.register": {
            "name": "stores.register",
            "description": "Register new OrderDesk store",
            "params": [
                {
                    "name": "store_name",
                    "type": "string",
                    "required": True,
                    "placeholder": "My Store",
                },
                {
                    "name": "store_id",
                    "type": "string",
                    "required": True,
                    "placeholder": "12345",
                },
                {
                    "name": "api_key",
                    "type": "password",
                    "required": True,
                    "placeholder": "Your API key",
                },
                {
                    "name": "label",
                    "type": "string",
                    "required": False,
                    "placeholder": "Production",
                },
            ],
        },
        "stores.list": {
            "name": "stores.list",
            "description": "List all registered stores",
            "params": [],
        },
        "stores.use_store": {
            "name": "stores.use_store",
            "description": "Set active store for session",
            "params": [
                {
                    "name": "store_name",
                    "type": "string",
                    "required": True,
                    "placeholder": "My Store",
                }
            ],
        },
        "stores.resolve": {
            "name": "stores.resolve",
            "description": "Resolve store by name (debug)",
            "params": [
                {
                    "name": "store_name",
                    "type": "string",
                    "required": True,
                    "placeholder": "My Store",
                }
            ],
        },
        "orders.get": {
            "name": "orders.get",
            "description": "Get order by ID (cached 15s)",
            "params": [
                {
                    "name": "order_id",
                    "type": "string",
                    "required": True,
                    "placeholder": "123456",
                }
            ],
        },
        "orders.list": {
            "name": "orders.list",
            "description": "List orders with pagination (cached 15s)",
            "params": [
                {
                    "name": "limit",
                    "type": "integer",
                    "required": False,
                    "placeholder": "50",
                },
                {
                    "name": "offset",
                    "type": "integer",
                    "required": False,
                    "placeholder": "0",
                },
                {
                    "name": "search",
                    "type": "string",
                    "required": False,
                    "placeholder": "customer@example.com",
                },
            ],
        },
        "orders.create": {
            "name": "orders.create",
            "description": "Create new order",
            "params": [
                {
                    "name": "order_data",
                    "type": "string",
                    "required": True,
                    "placeholder": '{"email": "customer@example.com", "order_items": [...]}',
                }
            ],
        },
        "orders.update": {
            "name": "orders.update",
            "description": "Update order (safe merge with retries)",
            "params": [
                {
                    "name": "order_id",
                    "type": "string",
                    "required": True,
                    "placeholder": "123456",
                },
                {
                    "name": "changes",
                    "type": "string",
                    "required": True,
                    "placeholder": '{"email": "newemail@example.com"}',
                },
            ],
        },
        "orders.delete": {
            "name": "orders.delete",
            "description": "Delete order",
            "params": [
                {
                    "name": "order_id",
                    "type": "string",
                    "required": True,
                    "placeholder": "123456",
                }
            ],
        },
        "products.get": {
            "name": "products.get",
            "description": "Get product by ID (cached 60s)",
            "params": [
                {
                    "name": "product_id",
                    "type": "string",
                    "required": True,
                    "placeholder": "product-123",
                }
            ],
        },
        "products.list": {
            "name": "products.list",
            "description": "List products with search (cached 60s)",
            "params": [
                {
                    "name": "limit",
                    "type": "integer",
                    "required": False,
                    "placeholder": "50",
                },
                {
                    "name": "offset",
                    "type": "integer",
                    "required": False,
                    "placeholder": "0",
                },
                {
                    "name": "search",
                    "type": "string",
                    "required": False,
                    "placeholder": "widget",
                },
            ],
        },
    }

    # Convert to list for dropdown
    tools = list(tools_dict.values())

    return get_templates().TemplateResponse(
        "console.html",
        {
            "request": request,
            "user": user,
            "tools": tools,
            "tools_json": json.dumps(tools_dict),
            "csrf_token": generate_csrf_token(),
        },
    )


@router.post("/console/execute")
async def execute_tool(
    request: Request,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Execute an MCP tool via the web console.

    Args:
        request: FastAPI request with JSON body
        user: Current authenticated user
        db: Database session

    Returns:
        JSON response with tool result
    """
    import json as json_module
    import time

    from mcp_server.routers import orders, products, stores

    try:
        # Parse request body
        body = await request.json()
        tool_name = body.get("tool_name")
        params = body.get("params", {})

        if not tool_name:
            return {"success": False, "error": "Tool name is required"}

        # Map tool names to actual MCP functions
        tool_map = {
            # Tenant tools
            "tenant.use_master_key": stores.use_master_key,
            # Store tools
            "stores.register": stores.register_store,
            "stores.list": stores.list_stores_mcp,
            "stores.use_store": stores.use_store,
            "stores.delete": stores.delete_store_mcp,
            "stores.resolve": stores.resolve_store,
            # Order tools
            "orders.get": orders.get_order_mcp,
            "orders.list": orders.list_orders_mcp,
            "orders.create": orders.create_order_mcp,
            "orders.update": orders.update_order_mcp,
            "orders.delete": orders.delete_order_mcp,
            # Product tools
            "products.get": products.get_product_mcp,
            "products.list": products.list_products_mcp,
        }

        tool_func = tool_map.get(tool_name)
        if not tool_func:
            return {
                "success": False,
                "error": f"Unknown tool: {tool_name}",
                "available_tools": list(tool_map.keys()),
            }

        # Execute tool
        start_time = time.perf_counter()

        # Parse JSON strings in params if needed (for order_data, changes, etc.)
        for key, value in params.items():
            if isinstance(value, str) and value.startswith("{"):
                try:
                    params[key] = json_module.loads(value)
                except json_module.JSONDecodeError:
                    pass  # Keep as string if not valid JSON

        # Call the tool
        result = await tool_func(params, db)

        duration_ms = (time.perf_counter() - start_time) * 1000

        return {
            "success": True,
            "tool": tool_name,
            "result": result,
            "duration_ms": round(duration_ms, 2),
            "timestamp": time.time(),
        }

    except Exception as e:
        logger.error("Tool execution error in WebUI console", error=str(e))
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
        }


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    user: dict = Depends(get_current_user),
):
    """
    Display settings page.

    Args:
        request: FastAPI request
        user: Current authenticated user

    Returns:
        Settings HTML page
    """
    config = {
        "cache_backend": settings.cache_backend,
        "enable_metrics": settings.enable_metrics,
        "enable_audit_log": settings.enable_audit_log,
        "log_level": settings.log_level,
        "session_timeout": settings.session_timeout,
        "version": "0.1.0-alpha",
    }

    return get_templates().TemplateResponse(
        "settings.html",
        {
            "request": request,
            "user": user,
            "config": config,
            "csrf_token": generate_csrf_token(),
        },
    )


# ============================================================================
# User Management Routes (Phase 6)
# ============================================================================


@router.get("/users", response_class=HTMLResponse)
async def user_list_page(
    request: Request,
    search: str | None = None,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Display user management page (master key holders only).

    Args:
        request: FastAPI request
        search: Optional search query (by email)
        user: Current authenticated user
        db: Database session

    Returns:
        User management HTML page
    """
    user_service = UserService(db)

    # Get all users
    users = await user_service.list_users(limit=100, search=search)

    # Calculate statistics
    total_stores = sum(u["store_count"] for u in users)
    active_today = sum(
        1
        for u in users
        if u["last_activity"]
        and (datetime.now(timezone.utc) - u["last_activity"]).days == 0
    )

    return get_templates().TemplateResponse(
        "users/list.html",
        {
            "request": request,
            "user": user,
            "users": users,
            "total_stores": total_stores,
            "active_today": active_today,
            "search": search,
            "current_user_id": user["id"],
            "csrf_token": generate_csrf_token(),
        },
    )


@router.get("/users/{user_id}", response_class=HTMLResponse)
async def user_details_page(
    request: Request,
    user_id: str,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Display user details page.

    Args:
        request: FastAPI request
        user_id: User/tenant ID
        user: Current authenticated user
        db: Database session

    Returns:
        User details HTML page
    """
    user_service = UserService(db)
    user_details = await user_service.get_user(user_id)

    if not user_details:
        return get_templates().TemplateResponse(
            "404.html",
            {"request": request, "message": "User not found"},
            status_code=404,
        )

    return get_templates().TemplateResponse(
        "users/details.html",
        {
            "request": request,
            "user": user,
            "user": user_details,
            "current_user_id": user["id"],
            "now": datetime.now(timezone.utc),
            "csrf_token": generate_csrf_token(),
        },
    )


@router.post("/users/{user_id}/delete")
async def delete_user(
    request: Request,
    user_id: str,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete user and all their data (cascade delete).

    Args:
        request: FastAPI request
        user_id: User/tenant ID to delete
        user: Current authenticated user
        db: Database session

    Returns:
        Redirect to user list
    """
    # Prevent self-deletion
    if user_id == user["id"]:
        logger.warning("User attempted to delete themselves", user_id=user_id)
        return RedirectResponse(
            url=f"/webui/users/{user_id}?error=cannot_delete_self",
            status_code=303,
        )

    user_service = UserService(db)
    success = await user_service.delete_user(user_id, deleted_by=user["id"])

    if success:
        logger.info("User deleted via WebUI", user_id=user_id, deleted_by=user["id"])
        return RedirectResponse(url="/webui/users?success=user_deleted", status_code=303)
    else:
        logger.warning("User deletion failed - not found", user_id=user_id)
        return RedirectResponse(
            url=f"/webui/users?error=user_not_found",
            status_code=303,
        )


# ============================================================================
# Public Signup Routes (Phase 6 - Sprint 3)
# ============================================================================


def get_email_service() -> EmailService | None:
    """Get configured email service based on settings."""
    if not settings.enable_public_signup:
        return None

    # Create provider based on configuration
    if settings.email_provider == "smtp":
        if not all([settings.smtp_host, settings.smtp_from_email]):
            logger.error("SMTP provider selected but not configured")
            return None

        provider = SMTPEmailProvider(
            host=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            use_tls=settings.smtp_use_tls,
            from_email=settings.smtp_from_email,
        )
    else:
        # Default to console provider for development
        provider = ConsoleEmailProvider(from_email="noreply@localhost")

    return EmailService(provider=provider)


@router.get("/signup", response_class=HTMLResponse)
async def signup_form(
    request: Request,
    error: str | None = None,
):
    """
    Display signup form (only if public signup is enabled).

    Args:
        request: FastAPI request
        error: Optional error message

    Returns:
        Signup form HTML page or 404 if signup disabled
    """
    if not settings.enable_public_signup:
        return get_templates().TemplateResponse(
            "404.html",
            {"request": request, "message": "Public signup is not enabled"},
            status_code=404,
        )

    csrf_token = generate_csrf_token()

    return get_templates().TemplateResponse(
        "signup/form.html",
        {
            "request": request,
            "csrf_token": csrf_token,
            "error": error,
            "email": request.query_params.get("email"),
        },
    )


@router.post("/signup")
async def signup(
    request: Request,
    email: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Process signup form submission.

    Args:
        request: FastAPI request
        email: Email address from form
        csrf_token: CSRF token from form
        db: Database session

    Returns:
        Redirect to verification pending page or signup form with error
    """
    if not settings.enable_public_signup:
        return RedirectResponse(url="/webui/login", status_code=303)

    # Get client IP for rate limiting
    client_host = request.client.host if request.client else "unknown"

    # Check rate limit
    rate_limit_service = RateLimitService(db)
    is_allowed, remaining = rate_limit_service.check_signup_rate_limit(
        ip_address=client_host,
        limit_per_hour=settings.signup_rate_limit_per_hour,
    )

    if not is_allowed:
        reset_time = rate_limit_service.get_rate_limit_reset_time(client_host)
        return get_templates().TemplateResponse(
            "signup/form.html",
            {
                "request": request,
                "csrf_token": generate_csrf_token(),
                "error": f"Rate limit exceeded. Too many signup attempts. Please try again later.",
                "email": email,
            },
            status_code=429,
        )

    # Check if email already exists
    from mcp_server.models.database import Tenant

    existing = db.query(Tenant).filter(Tenant.email == email).first()
    if existing:
        return get_templates().TemplateResponse(
            "signup/form.html",
            {
                "request": request,
                "csrf_token": generate_csrf_token(),
                "error": "An account with this email already exists. Please log in instead.",
                "email": email,
            },
            status_code=400,
        )

    # Generate magic link
    magic_link_service = MagicLinkService(db)
    token, token_hash = magic_link_service.generate_magic_link(
        email=email,
        purpose="email_verification",
        ip_address=client_host,
        expiry_seconds=settings.signup_verification_expiry,
    )

    # Generate verification link
    base_url = str(request.base_url).rstrip("/")
    verification_link = f"{base_url}/webui/verify/{token}"

    # Send verification email
    email_service = get_email_service()
    if email_service and email_service.is_enabled():
        success = await email_service.send_verification_email(
            to=email,
            verification_link=verification_link,
            master_key=None,  # Master key generated after verification
        )

        if not success:
            logger.error("Failed to send verification email", email=email)
            return get_templates().TemplateResponse(
                "signup/form.html",
                {
                    "request": request,
                    "csrf_token": generate_csrf_token(),
                    "error": "Failed to send verification email. Please try again.",
                    "email": email,
                },
                status_code=500,
            )
    else:
        logger.error("Email service not configured")
        return get_templates().TemplateResponse(
            "signup/form.html",
            {
                "request": request,
                "csrf_token": generate_csrf_token(),
                "error": "Email service not configured. Please contact administrator.",
                "email": email,
            },
            status_code=500,
        )

    logger.info("Signup verification email sent", email=email, ip=client_host)

    # Redirect to verification pending page
    return get_templates().TemplateResponse(
        "signup/verify_pending.html",
        {
            "request": request,
            "email": email,
        },
    )


@router.get("/verify/{token}")
async def verify_email(
    request: Request,
    token: str,
    db: Session = Depends(get_db),
):
    """
    Verify email address and create account.

    Args:
        request: FastAPI request
        token: Magic link token from URL
        db: Database session

    Returns:
        Success page with master key or error page
    """
    if not settings.enable_public_signup:
        return RedirectResponse(url="/webui/login", status_code=303)

    # Verify magic link
    magic_link_service = MagicLinkService(db)
    success, email, tenant_id = magic_link_service.verify_magic_link(
        token=token,
        purpose="email_verification",
    )

    if not success or not email:
        logger.warning("Email verification failed", token=token[:8])
        return get_templates().TemplateResponse(
            "signup/form.html",
            {
                "request": request,
                "csrf_token": generate_csrf_token(),
                "error": "Verification link is invalid or has expired. Please sign up again.",
            },
            status_code=400,
        )

    # Check if user already exists (shouldn't happen, but double-check)
    from mcp_server.models.database import Tenant

    existing = db.query(Tenant).filter(Tenant.email == email).first()
    if existing:
        logger.warning("User already exists during verification", email=email)
        return RedirectResponse(url="/webui/login?error=already_exists", status_code=303)

    # Generate master key
    master_key = generate_master_key(length=48)  # 64-char URL-safe string

    # Hash master key
    master_key_hash, salt = hash_master_key(master_key)

    # Create tenant
    tenant = Tenant(
        master_key_hash=master_key_hash,
        salt=salt,
        email=email,
        email_verified=True,  # Just verified
        last_login=None,
        last_activity=None,
    )

    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    logger.info(
        "Account created via public signup",
        email=email,
        tenant_id=tenant.id,
    )

    # Send welcome email (optional, don't fail if it doesn't work)
    email_service = get_email_service()
    if email_service and email_service.is_enabled():
        try:
            await email_service.send_welcome_email(
                to=email,
                master_key=master_key,
            )
        except Exception as e:
            logger.error("Failed to send welcome email", error=str(e), email=email)
            # Don't fail the signup if welcome email fails

    # Show success page with master key (ONE TIME ONLY)
    return get_templates().TemplateResponse(
        "signup/success.html",
        {
            "request": request,
            "email": email,
            "master_key": master_key,
        },
    )


# Add root redirect
@router.get("/", response_class=RedirectResponse)
async def root():
    """Redirect root to login or dashboard."""
    return RedirectResponse(url="/webui/login")
