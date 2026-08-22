from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .decorators import workspace_required
from .forms import (
    ProductForm,
    PurchaseOrderForm,
    PurchaseOrderItemForm,
    SignupForm,
    StockMovementForm,
    SupplierForm,
)
from .models import Product, PurchaseOrder, StockMovement, Supplier


def landing(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "inventory/landing.html")


def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Your ShelfWise workspace is ready.")
        return redirect("dashboard")
    return render(request, "registration/signup.html", {"form": form})


def scoped_products(organization):
    return Product.objects.filter(organization=organization).select_related("supplier")


@workspace_required
def dashboard(request):
    products = list(scoped_products(request.organization))
    low_stock = [product for product in products if product.needs_reorder]
    open_orders = PurchaseOrder.objects.filter(organization=request.organization).exclude(
        status__in=[PurchaseOrder.Status.RECEIVED, PurchaseOrder.Status.CANCELLED]
    )
    context = {
        "product_count": len(products),
        "units_on_hand": sum(product.quantity_on_hand for product in products),
        "inventory_value": sum((product.stock_value for product in products), Decimal("0")),
        "low_stock": low_stock,
        "open_orders": open_orders[:5],
        "recent_movements": StockMovement.objects.filter(
            organization=request.organization
        ).select_related("product", "created_by")[:8],
    }
    return render(request, "inventory/dashboard.html", context)


@workspace_required
def products(request):
    query = request.GET.get("q", "").strip()
    rows = scoped_products(request.organization)
    if query:
        rows = rows.filter(name__icontains=query) | rows.filter(sku__icontains=query)
    form = ProductForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        product = form.save(commit=False)
        product.organization = request.organization
        product.save()
        messages.success(request, "Product added to the catalog.")
        return redirect("products")
    return render(
        request, "inventory/products.html", {"products": rows, "form": form, "query": query}
    )


@workspace_required
def suppliers(request):
    form = SupplierForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        supplier = form.save(commit=False)
        supplier.organization = request.organization
        supplier.save()
        messages.success(request, "Supplier added.")
        return redirect("suppliers")
    rows = Supplier.objects.filter(organization=request.organization)
    return render(request, "inventory/suppliers.html", {"suppliers": rows, "form": form})


@workspace_required
def movements(request):
    form = StockMovementForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        movement = form.save(commit=False)
        movement.organization = request.organization
        movement.created_by = request.user
        movement.save()
        messages.success(request, "Stock movement recorded.")
        return redirect("movements")
    rows = StockMovement.objects.filter(organization=request.organization).select_related(
        "product", "created_by"
    )
    return render(request, "inventory/movements.html", {"movements": rows, "form": form})


@workspace_required
def purchase_orders(request):
    form = PurchaseOrderForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        order = form.save(commit=False)
        order.organization = request.organization
        order.save()
        messages.success(request, "Purchase order created. Add its line items next.")
        return redirect("purchase_order_detail", pk=order.pk)
    rows = PurchaseOrder.objects.filter(organization=request.organization).select_related(
        "supplier"
    )
    return render(request, "inventory/purchase_orders.html", {"orders": rows, "form": form})


@workspace_required
def purchase_order_detail(request, pk):
    order = get_object_or_404(
        PurchaseOrder.objects.select_related("supplier").prefetch_related("items__product"),
        pk=pk,
        organization=request.organization,
    )
    editable = order.status in [PurchaseOrder.Status.DRAFT, PurchaseOrder.Status.ORDERED]
    form = PurchaseOrderItemForm(
        request.POST or None, organization=request.organization, supplier=order.supplier
    )
    if request.method == "POST":
        if not editable:
            messages.error(request, "Closed purchase orders cannot be changed.")
            return redirect("purchase_order_detail", pk=pk)
        if form.is_valid():
            product = form.cleaned_data["product"]
            if order.items.filter(product=product).exists():
                form.add_error("product", "This product is already on the purchase order.")
            else:
                item = form.save(commit=False)
                item.purchase_order = order
                item.save()
                messages.success(request, "Line item added.")
                return redirect("purchase_order_detail", pk=pk)
    return render(
        request,
        "inventory/purchase_order_detail.html",
        {"order": order, "form": form, "editable": editable},
    )


@require_POST
@workspace_required
@transaction.atomic
def receive_purchase_order(request, pk):
    order = get_object_or_404(
        PurchaseOrder.objects.select_for_update().prefetch_related("items"),
        pk=pk,
        organization=request.organization,
    )
    if order.status == PurchaseOrder.Status.RECEIVED:
        messages.info(request, "This purchase order was already received.")
    elif order.status == PurchaseOrder.Status.CANCELLED:
        messages.error(request, "A cancelled purchase order cannot be received.")
    elif not order.items.exists():
        messages.error(request, "Add at least one item before receiving this order.")
    else:
        for item in order.items.all():
            StockMovement.objects.create(
                organization=request.organization,
                product=item.product,
                kind=StockMovement.Kind.RECEIPT,
                quantity=item.quantity,
                reference=order.number,
                note="Received from purchase order",
                created_by=request.user,
            )
        order.status = PurchaseOrder.Status.RECEIVED
        order.save(update_fields=["status"])
        messages.success(request, "Purchase order received and stock updated.")
    return redirect("purchase_order_detail", pk=pk)


@workspace_required
def api_summary(request):
    products = list(scoped_products(request.organization))
    return JsonResponse(
        {
            "workspace": request.organization.name,
            "products": len(products),
            "units_on_hand": sum(product.quantity_on_hand for product in products),
            "low_stock": sum(product.needs_reorder for product in products),
            "open_purchase_orders": PurchaseOrder.objects.filter(
                organization=request.organization,
                status__in=[PurchaseOrder.Status.DRAFT, PurchaseOrder.Status.ORDERED],
            ).count(),
        }
    )


@workspace_required
def api_products(request):
    results = [
        {
            "id": product.id,
            "sku": product.sku,
            "name": product.name,
            "quantity_on_hand": product.quantity_on_hand,
            "reorder_level": product.reorder_level,
            "needs_reorder": product.needs_reorder,
            "stock_value": str(product.stock_value),
        }
        for product in scoped_products(request.organization)
    ]
    return JsonResponse({"results": results})


@workspace_required
def api_movements(request):
    rows = StockMovement.objects.filter(organization=request.organization).select_related("product")
    return JsonResponse(
        {
            "results": [
                {
                    "id": row.id,
                    "sku": row.product.sku,
                    "kind": row.kind,
                    "quantity": row.quantity,
                    "reference": row.reference,
                    "created_at": row.created_at,
                }
                for row in rows
            ]
        }
    )
