"""WebUI routes for OrderDesk MCP Server admin interface."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from mcp_server.config import settings
from mcp_server.models.database import get_db
from mcp_server.services.store import StoreService
from mcp_server.utils.logging import logger
from mcp_server.webui.auth import (
    auth_manager,
    create_session_cookie,
    generate_csrf_token,
    get_current_user,
)

router = APIRouter(prefix="/webui", tags=["webui"])

# Configure Jinja2 templates
templates = Jinja2Templates(directory="mcp_server/templates")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Display login page."""
    csrf_token = generate_csrf_token()

    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "csrf_token": csrf_token,
            "error": None,
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
        return templates.TemplateResponse(
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

    return templates.TemplateResponse(
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

    return templates.TemplateResponse(
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
    return templates.TemplateResponse(
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

        return templates.TemplateResponse(
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
        logger.info(
            "Store deleted via WebUI", tenant_id=tenant_id, store_id=store_id
        )
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

    return templates.TemplateResponse(
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

    return templates.TemplateResponse(
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
        return RedirectResponse(
            url=f"/webui/stores/{store_id}", status_code=303
        )

    except Exception as e:
        logger.error("Failed to update store via WebUI", error=str(e))
        db.rollback()

        return templates.TemplateResponse(
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
                {"name": "order_id", "type": "string", "required": True, "placeholder": "123456"},
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

    return templates.TemplateResponse(
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

    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "user": user,
            "config": config,
            "csrf_token": generate_csrf_token(),
        },
    )


# Add root redirect
@router.get("/", response_class=RedirectResponse)
async def root():
    """Redirect root to login or dashboard."""
    return RedirectResponse(url="/webui/login")

