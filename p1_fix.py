from flask import request, jsonify
from sqlalchemy.exc import IntegrityError, OperationalError
from decimal import Decimal

# Assuming 'app' is your Flask application instance and 'db' is your SQLAlchemy instance
# from your_app import app, db
# Assuming 'Product' and 'Inventory' are your SQLAlchemy models
# from your_models import Product, Inventory

@app.route('/api/products', methods=['POST'])
def create_product():
    # FIX: Ensure the request body is JSON and catch parsing errors early
    if not request.is_json:
        return jsonify({"message": "Request must be JSON"}), 400

    data = request.json

    # FIX: Define and validate all mandatory input fields upfront
    required_product_fields = ['name', 'sku', 'price']
    required_inventory_fields = ['warehouse_id', 'initial_quantity']

    missing_product_fields = [field for field in required_product_fields if field not in data]
    if missing_product_fields:
        return jsonify({"message": f"Missing required product fields: {', '.join(missing_product_fields)}"}), 400

    missing_inventory_fields = [field for field in required_inventory_fields if field not in data]
    if missing_inventory_fields:
        return jsonify({"message": f"Missing required initial inventory fields: {', '.join(missing_inventory_fields)}"}), 400

    # FIX: Robust type validation and conversion for numeric fields
    try:
        product_name = data['name']
        product_sku = data['sku']
        # FIX: Convert price to Decimal for financial accuracy, as price can be decimal values
        product_price = Decimal(str(data['price']))

        initial_warehouse_id = int(data['warehouse_id'])
        initial_quantity = int(data['initial_quantity'])

        # FIX: Basic business validation for quantity
        if initial_quantity < 0:
            return jsonify({"message": "Initial quantity cannot be negative."}), 400

    except (ValueError, TypeError) as e:
        # FIX: Catch specific errors for invalid data types and provide clear feedback
        return jsonify({"message": f"Invalid data type provided: {e}. Please ensure price is numeric, and IDs/quantities are integers."}), 400
    except Exception as e:
        # FIX: Catch any other unexpected data parsing errors
        return jsonify({"message": f"Error processing input data: {e}"}), 400


    # FIX: Business Logic: Enforce SKU uniqueness before attempting creation
    try:
        existing_product = Product.query.filter_by(sku=product_sku).first()
        if existing_product:
            # FIX: Return 409 Conflict status code for unique constraint violation
            return jsonify({"message": f"Product with SKU '{product_sku}' already exists. SKUs must be unique across the platform."}), 409
    except OperationalError as e:
        # FIX: Handle database connection issues during SKU check
        return jsonify({"message": f"Database error during SKU uniqueness check: {e}"}), 500


    # FIX: Implement atomic database operations using a single transaction
    try:
        # FIX: Create Product without warehouse_id directly. Product definition is independent of location.
        product = Product(
            name=product_name,
            sku=product_sku,
            price=product_price
        )
        db.session.add(product)
        # FIX: Use flush() to get product.id (for auto-incrementing PKs) before commit
        db.session.flush()

        # FIX: Create initial Inventory record linking product to its quantity in a specific warehouse
        inventory = Inventory(
            product_id=product.id,
            warehouse_id=initial_warehouse_id,
            quantity=initial_quantity
        )
        db.session.add(inventory)

        # FIX: Commit both product and inventory creation as a single, atomic transaction
        db.session.commit()

        # FIX: Return 201 Created status for successful resource creation
        return jsonify({"message": "Product created successfully", "product_id": str(product.id)}), 201

    except IntegrityError as e:
        db.session.rollback() # FIX: Rollback transaction on integrity errors
        if "Duplicate entry" in str(e) or "UNIQUE constraint failed" in str(e):
             return jsonify({"message": f"Database integrity error: A duplicate entry was detected (e.g., SKU already exists or warehouse ID is invalid). Details: {e}"}), 409
        return jsonify({"message": f"Database integrity error: {e}"}), 400
    except OperationalError as e:
        db.session.rollback() # FIX: Rollback on database connection/operational errors
        return jsonify({"message": f"Database connection or operation failed: {e}"}), 500
    except Exception as e:
        db.session.rollback() # FIX: Rollback on any other unexpected server-side error
        return jsonify({"message": f"An unexpected server error occurred: {e}"}), 500
