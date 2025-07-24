from flask import jsonify, Blueprint
from datetime import datetime, timedelta
from sqlalchemy import func, desc

# Assuming these are your configured Flask app.py and SQLAlchemy models.py
from app import db
from models import Company, Warehouse, Product, Inventory, Supplier, InvChange, ProductType

api_bp = Blueprint('api', __name__)

@api_bp.route("/api/companies/<string:company_id>/alerts/low-stock", methods=['GET'])
def get_low_stock_alerts(company_id):
    # Retrieve company, return 404 if not found
    company = Company.query.filter_by(id=company_id).first()
    if not company:
        return jsonify({"message": "Company not found"}), 404

    # Define the period for "recent sales activity"
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    alerts = []

    # Query for all inventory items belonging to the company's warehouses
    # that are currently below their defined low_stock_threshold.
    # Must handle multiple warehouses per company.
    low_stock_inventories = (
        db.session.query(Inventory)
        .join(Warehouse, Inventory.warehouse_id == Warehouse.id)
        .join(Product, Inventory.product_id == Product.id)
        .join(ProductType, Product.type_id == ProductType.id)
        .filter(Warehouse.company_id == company_id)
        .filter(Inventory.quantity < ProductType.low_stock_threshold) # Threshold varies by product type
        .all()
    )

    for inv in low_stock_inventories:
        # Check for recent sales activity for this specific inventory item (last 30 days)
        # Inferring sales from 'invchange' where new_quantity < old_quantity
        recent_sales_count = db.session.query(InvChange).filter(
            InvChange.inventory_id == inv.id,
            InvChange.changed_at >= thirty_days_ago,
            InvChange.new_quantity < InvChange.old_quantity # Assuming quantity decrease means a sale
        ).count()

        # Only alert for products with recent sales activity as per business rule
        if recent_sales_count == 0:
            continue

        # Calculate Days Until Stockout: Determine average daily sales over the recent period.
        avg_daily_sales = db.session.query(
            func.avg(func.abs(InvChange.old_quantity - InvChange.new_quantity)) # Calculate the average of the absolute quantity change
        ).filter(
            InvChange.inventory_id == inv.id,
            InvChange.changed_at >= thirty_days_ago,
            InvChange.new_quantity < InvChange.old_quantity # Only consider decreases for sales calculation
        ).scalar() or 0.0 # Use .scalar() to get the single average value, default to 0.0 if no relevant sales records.

        days_until_stockout = 999 # Arbitrary large number if no sales or very low sales
        if avg_daily_sales > 0:
            days_until_stockout = int(inv.quantity / avg_daily_sales)

        # Retrieve associated Product, Warehouse, and Supplier information
        # Include supplier information for reordering.
        product = Product.query.get(inv.product_id)
        warehouse = Warehouse.query.get(inv.warehouse_id)
        product_type = ProductType.query.get(product.type_id)

        # Get supplier information directly from product.supplier_id as per ERD
        supplier_info = { "id": None, "name": "No Supplier", "contact_email": None }
        if product.supplier_id:
            supplier = Supplier.query.get(product.supplier_id)
            if supplier:
                supplier_info = {
                    "id": str(supplier.id),
                    "name": supplier.name,
                    "contact_email": supplier.contact_email
                }

        # Construct the alert object in the specified format
        alert_obj = {
            "product_id": str(product.id),
            "product_name": product.name,
            "sku": product.sku,
            "warehouse_id": str(warehouse.id),
            "warehouse_name": warehouse.name,
            "current_stock": inv.quantity,
            "threshold": product_type.low_stock_threshold,
            "days_until_stockout": days_until_stockout,
            "supplier": supplier_info
        }
        alerts.append(alert_obj)

    # Return the final list of alerts and total count
    return jsonify({
        "alerts": alerts,
        "total_alerts": len(alerts)
    }), 200
