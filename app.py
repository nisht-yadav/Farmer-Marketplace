from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import mysql.connector
from datetime import datetime
import json

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# Database configuration
DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 3306,
    'user': 'root',
    'password': 'nisht',
    'database': 'marketplacedb'
}

def get_db():
    return mysql.connector.connect(**DB_CONFIG)

def update_product_rating(product_id):
    """Calculate and update the average rating for a product"""
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT AVG(rating) as avg_rating
        FROM Review
        WHERE productId = %s
    """, (product_id,))
    
    result = cursor.fetchone()
    avg_rating = result['avg_rating'] if result['avg_rating'] else 0
    
    cursor.execute("""
        UPDATE Product
        SET averageRating = %s
        WHERE id = %s
    """, (avg_rating, product_id))
    
    db.commit()
    cursor.close()
    db.close()

# Decorator for login required
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Decorator for farmer only
def farmer_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('role') != 'FARMER':
            flash('Access denied. Farmers only.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# Decorator for buyer only
def buyer_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('role') != 'BUYER':
            flash('Access denied. Buyers only.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== AUTH ROUTES ====================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        phone = request.form.get('phone', '')
        location = request.form.get('location', '')
        role = request.form['role']
        
        # Validate role
        if role not in ['FARMER', 'BUYER']:
            flash('Invalid role selected', 'error')
            return redirect(url_for('register'))
        
        hashed_password = generate_password_hash(password)
        
        db = get_db()
        cursor = db.cursor()
        
        try:
            # Insert user
            cursor.execute("""
                INSERT INTO User (name, email, password, phone, location, role)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (name, email, hashed_password, phone, location, role))
            
            user_id = cursor.lastrowid
            
            # Create corresponding Farmer or Buyer record
            if role == 'FARMER':
                cursor.execute("INSERT INTO Farmer (userId) VALUES (%s)", (user_id,))
            else:
                cursor.execute("INSERT INTO Buyer (userId) VALUES (%s)", (user_id,))
            
            db.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
            
        except mysql.connector.IntegrityError:
            flash('Email already exists', 'error')
            return redirect(url_for('register'))
        finally:
            cursor.close()
            db.close()
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        db = get_db()
        cursor = db.cursor(dictionary=True)
        
        cursor.execute("SELECT * FROM User WHERE email = %s", (email,))
        user = cursor.fetchone()
        
        cursor.close()
        db.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['name'] = user['name']
            session['role'] = user['role']
            
            flash(f'Welcome {user["name"]}!', 'success')
            
            if user['role'] == 'FARMER':
                return redirect(url_for('farmer_dashboard'))
            else:
                return redirect(url_for('buyer_dashboard'))
        else:
            flash('Invalid email or password', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))

# ==================== FARMER ROUTES ====================

@app.route('/farmer/dashboard')
@farmer_required
def farmer_dashboard():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    # Get farmer info
    cursor.execute("""
        SELECT f.*, u.name, u.email 
        FROM Farmer f 
        JOIN User u ON f.userId = u.id 
        WHERE u.id = %s
    """, (session['user_id'],))
    farmer = cursor.fetchone()
    
    # Get farmer's products
    cursor.execute("""
        SELECT * FROM Product 
        WHERE farmerId = %s 
        ORDER BY createdAt DESC
    """, (session['user_id'],))
    products = cursor.fetchall()
    
    # Get farmer's payouts and lifetime earnings
    cursor.execute("""
        SELECT * FROM Payout 
        WHERE farmerId = (SELECT id FROM Farmer WHERE userId = %s)
        ORDER BY createdAt DESC
    """, (session['user_id'],))
    payouts = cursor.fetchall()
    
    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0) as lifetime_earnings
        FROM Payout 
        WHERE farmerId = (SELECT id FROM Farmer WHERE userId = %s)
    """, (session['user_id'],))
    earnings_result = cursor.fetchone()
    lifetime_earnings = earnings_result['lifetime_earnings'] if earnings_result else 0
    
    cursor.close()
    db.close()
    
    return render_template('farmer_dashboard.html', farmer=farmer, products=products, payouts=payouts, lifetime_earnings=lifetime_earnings)

@app.route('/farmer/products/add', methods=['GET', 'POST'])
@farmer_required
def add_product():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = float(request.form['price'])
        stock = int(request.form['stock'])
        
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("""
            INSERT INTO Product (farmerId, name, description, price, stockQuantity)
            VALUES (%s, %s, %s, %s, %s)
        """, (session['user_id'], name, description, price, stock))
        
        db.commit()
        cursor.close()
        db.close()
        
        flash('Product added successfully!', 'success')
        return redirect(url_for('farmer_dashboard'))
    
    return render_template('add_product.html')

@app.route('/farmer/products/<int:product_id>/edit', methods=['GET', 'POST'])
@farmer_required
def edit_product(product_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    # Verify ownership
    cursor.execute("SELECT * FROM Product WHERE id = %s AND farmerId = %s", 
                   (product_id, session['user_id']))
    product = cursor.fetchone()
    
    if not product:
        flash('Product not found', 'error')
        return redirect(url_for('farmer_dashboard'))
    
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = float(request.form['price'])
        stock = int(request.form['stock'])
        available = 'available' in request.form
        
        cursor.execute("""
            UPDATE Product 
            SET name=%s, description=%s, price=%s, stockQuantity=%s, isAvailable=%s
            WHERE id=%s
        """, (name, description, price, stock, available, product_id))
        
        db.commit()
        cursor.close()
        db.close()
        
        flash('Product updated successfully!', 'success')
        return redirect(url_for('farmer_dashboard'))
    
    cursor.close()
    db.close()
    
    return render_template('edit_product.html', product=product)

@app.route('/farmer/orders')
@farmer_required
def farmer_orders():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    # Get all order items for this farmer's products with delivery details
    cursor.execute("""
        SELECT 
            oi.id as order_item_id,
            oi.orderId,
            oi.quantity,
            oi.price,
            oi.deliveryStatus,
            oi.deliveredAt,
            p.id as product_id,
            p.name as product_name,
            o.createdAt as order_date,
            o.deliveryAddress,
            o.totalAmount as order_total,
            u.name as buyer_name,
            u.email as buyer_email,
            u.phone as buyer_phone
        FROM OrderItem oi
        JOIN Product p ON oi.productId = p.id
        JOIN `Order` o ON oi.orderId = o.id
        JOIN User u ON o.userId = u.id
        WHERE p.farmerId = %s
        ORDER BY o.createdAt DESC, oi.id ASC
    """, (session['user_id'],))
    
    order_items = cursor.fetchall()
    
    cursor.close()
    db.close()
    
    return render_template('farmer_orders.html', order_items=order_items)

@app.route('/farmer/orders/mark-delivered/<int:order_item_id>', methods=['POST'])
@farmer_required
def mark_as_delivered(order_item_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    try:
        # Verify this order item belongs to farmer's product
        cursor.execute("""
            SELECT oi.*, p.farmerId, o.checkoutId
            FROM OrderItem oi
            JOIN Product p ON oi.productId = p.id
            JOIN `Order` o ON oi.orderId = o.id
            WHERE oi.id = %s
        """, (order_item_id,))
        
        order_item = cursor.fetchone()
        
        if not order_item:
            flash('Order item not found', 'error')
            return redirect(url_for('farmer_orders'))
        
        if order_item['farmerId'] != session['user_id']:
            flash('Unauthorized action', 'error')
            return redirect(url_for('farmer_orders'))
        
        if order_item['deliveryStatus'] == 'delivered':
            flash('Item already marked as delivered', 'info')
            return redirect(url_for('farmer_orders'))
        
        # Mark item as delivered
        cursor.execute("""
            UPDATE OrderItem
            SET deliveryStatus = 'delivered', deliveredAt = %s
            WHERE id = %s
        """, (datetime.now(), order_item_id))
        
        # Check if all items in this order for this farmer are delivered
        cursor.execute("""
            SELECT COUNT(*) as total_items,
                   SUM(CASE WHEN deliveryStatus = 'delivered' THEN 1 ELSE 0 END) as delivered_items
            FROM OrderItem oi
            JOIN Product p ON oi.productId = p.id
            WHERE oi.orderId = %s AND p.farmerId = %s
        """, (order_item['orderId'], session['user_id']))
        
        delivery_stats = cursor.fetchone()
        
        # If all items delivered, mark related payouts as transferred
        if delivery_stats['total_items'] == delivery_stats['delivered_items']:
            cursor.execute("""
                SELECT id FROM Farmer WHERE userId = %s
            """, (session['user_id'],))
            farmer_record = cursor.fetchone()
            
            if farmer_record:
                # Find payouts for this order/checkout and mark as transferred
                cursor.execute("""
                    UPDATE Payout
                    SET status = 'transferred'
                    WHERE farmerId = %s 
                    AND status = 'pending'
                    AND createdAt >= (SELECT createdAt FROM `Order` WHERE id = %s)
                    AND createdAt <= DATE_ADD((SELECT createdAt FROM `Order` WHERE id = %s), INTERVAL 1 HOUR)
                """, (farmer_record['id'], order_item['orderId'], order_item['orderId']))
        
        db.commit()
        flash('Item marked as delivered successfully!', 'success')
        
    except Exception as e:
        db.rollback()
        flash(f'Error marking item as delivered: {str(e)}', 'error')
    finally:
        cursor.close()
        db.close()
    
    return redirect(url_for('farmer_orders'))

# ==================== BUYER ROUTES ====================

@app.route('/buyer/dashboard')
@buyer_required
def buyer_dashboard():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    # Get all available products
    cursor.execute("""
        SELECT p.*, u.name as farmer_name, f.rating as farmer_rating
        FROM Product p
        JOIN User u ON p.farmerId = u.id
        JOIN Farmer f ON f.userId = u.id
        WHERE p.isAvailable = TRUE AND p.stockQuantity > 0
        ORDER BY p.createdAt DESC
    """)
    products = cursor.fetchall()
    
    cursor.close()
    db.close()
    
    return render_template('buyer_dashboard.html', products=products)

@app.route('/buyer/cart')
@buyer_required
def view_cart():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT c.*, p.name, p.price, p.stockQuantity, u.name as farmer_name
        FROM Cart c
        JOIN Product p ON c.productId = p.id
        JOIN User u ON p.farmerId = u.id
        WHERE c.userId = %s
    """, (session['user_id'],))
    
    cart_items = cursor.fetchall()
    total = sum(item['price'] * item['quantity'] for item in cart_items)
    
    cursor.close()
    db.close()
    
    return render_template('cart.html', cart_items=cart_items, total=total)

@app.route('/buyer/cart/add/<int:product_id>', methods=['POST'])
@buyer_required
def add_to_cart(product_id):
    quantity = int(request.form.get('quantity', 1))
    
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    # Check if product exists and is available
    cursor.execute("SELECT * FROM Product WHERE id = %s", (product_id,))
    product = cursor.fetchone()
    
    if not product or not product['isAvailable'] or product['stockQuantity'] < quantity:
        flash('Product not available', 'error')
        return redirect(url_for('buyer_dashboard'))
    
    # Check if already in cart
    cursor.execute("SELECT * FROM Cart WHERE userId = %s AND productId = %s", 
                   (session['user_id'], product_id))
    existing = cursor.fetchone()
    
    if existing:
        cursor.execute("""
            UPDATE Cart SET quantity = quantity + %s 
            WHERE userId = %s AND productId = %s
        """, (quantity, session['user_id'], product_id))
    else:
        cursor.execute("""
            INSERT INTO Cart (userId, productId, quantity)
            VALUES (%s, %s, %s)
        """, (session['user_id'], product_id, quantity))
    
    db.commit()
    cursor.close()
    db.close()
    
    flash('Added to cart!', 'success')
    return redirect(url_for('buyer_dashboard'))

@app.route('/buyer/cart/remove/<int:cart_id>', methods=['POST'])
@buyer_required
def remove_from_cart(cart_id):
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("DELETE FROM Cart WHERE id = %s AND userId = %s", 
                   (cart_id, session['user_id']))
    
    db.commit()
    cursor.close()
    db.close()
    
    flash('Removed from cart', 'success')
    return redirect(url_for('view_cart'))

@app.route('/buyer/checkout', methods=['GET', 'POST'])
@buyer_required
def checkout():
    # Show checkout page with cart summary on GET
    if request.method == 'GET':
        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT c.*, p.name as product_name, p.price, p.stockQuantity
            FROM Cart c
            JOIN Product p ON c.productId = p.id
            WHERE c.userId = %s
        """, (session['user_id'],))
        cart_items = cursor.fetchall()

        total = sum(item['price'] * item['quantity'] for item in cart_items) if cart_items else 0.0
        delivery_fee = float(total) / 10.0 if total else 0.0
        grand_total = total + delivery_fee

        cursor.close()
        db.close()

        return render_template('checkout.html', cart_items=cart_items, total=total, delivery_fee=delivery_fee, grand_total=grand_total)

    # Create checkout and redirect to payment on POST
    if request.method == 'POST':
        db = get_db()
        cursor = db.cursor(dictionary=True)

        try:
            # Get cart items
            cursor.execute("""
                SELECT c.*, p.price, p.stockQuantity, p.name as product_name
                FROM Cart c
                JOIN Product p ON c.productId = p.id
                WHERE c.userId = %s
            """, (session['user_id'],))
            cart_items = cursor.fetchall()

            if not cart_items:
                flash('Cart is empty', 'error')
                return redirect(url_for('view_cart'))

            # Validate stock
            for item in cart_items:
                if item['stockQuantity'] < item['quantity']:
                    flash(f'Insufficient stock for {item["product_name"]}', 'error')
                    return redirect(url_for('view_cart'))

            # Calculate total
            total = sum(item['price'] * item['quantity'] for item in cart_items)
            delivery_fee = float(total) / 10.0
            grand_total = total + delivery_fee

            # Create checkout record
            cursor.execute("""
                INSERT INTO Checkout (customerId, grandTotal, deliveryFee)
                VALUES (%s, %s, %s)
            """, (session['user_id'], grand_total, delivery_fee))
            checkout_id = cursor.lastrowid

            # Store checkout info in session for payment page
            session['pending_checkout'] = {
                'checkout_id': checkout_id,
                'subtotal': total,
                'delivery_fee': delivery_fee,
                'total_amount': grand_total
            }

            db.commit()
            cursor.close()
            db.close()

            # Redirect to payment page
            return redirect(url_for('payment_page'))

        except Exception as e:
            db.rollback()
            flash(f'Error processing checkout: {str(e)}', 'error')
            return redirect(url_for('view_cart'))
        finally:
            cursor.close()
            db.close()

    # Fallback
    return redirect(url_for('view_cart'))

@app.route('/buyer/payment')
@buyer_required
def payment_page():
    # Check if there's a pending checkout
    if 'pending_checkout' not in session:
        flash('No pending checkout found', 'error')
        return redirect(url_for('view_cart'))
    
    checkout_info = session['pending_checkout']
    
    return render_template('payment.html',
                         checkout_id=checkout_info['checkout_id'],
                         subtotal=checkout_info['subtotal'],
                         delivery_fee=checkout_info['delivery_fee'],
                         total_amount=checkout_info['total_amount'])

@app.route('/buyer/payment/process', methods=['POST'])
@buyer_required
def process_payment():
    import random
    import string
    
    if 'pending_checkout' not in session:
        flash('No pending checkout found', 'error')
        return redirect(url_for('view_cart'))
    
    checkout_info = session['pending_checkout']
    checkout_id = checkout_info['checkout_id']
    payment_method = request.form.get('payment_method')
    
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    try:
        # Get cart items
        cursor.execute("""
            SELECT c.*, p.price, p.stockQuantity, p.farmerId
            FROM Cart c
            JOIN Product p ON c.productId = p.id
            WHERE c.userId = %s
        """, (session['user_id'],))
        cart_items = cursor.fetchall()
        
        if not cart_items:
            flash('Cart is empty', 'error')
            return redirect(url_for('view_cart'))
        
        # Get user's delivery address
        cursor.execute("""
            SELECT location FROM User WHERE id = %s
        """, (session['user_id'],))
        user_info = cursor.fetchone()
        delivery_address = user_info['location'] if user_info and user_info['location'] else 'No address provided'
        
        # Generate fake transaction ID (simulating payment gateway)
        transaction_id = 'TXN' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
        
        # Create order with delivery address
        cursor.execute("""
            INSERT INTO `Order` (userId, totalAmount, deliveryAddress, checkoutId, status)
            VALUES (%s, %s, %s, %s, %s)
        """, (session['user_id'], checkout_info['total_amount'], delivery_address, checkout_id, 'completed'))
        order_id = cursor.lastrowid
        
        # Create order items and update stock
        for item in cart_items:
            if item['stockQuantity'] < item['quantity']:
                raise Exception(f'Insufficient stock for product ID {item["productId"]}')
            
            # Insert order item with delivery status
            cursor.execute("""
                INSERT INTO OrderItem (orderId, productId, quantity, price, deliveryStatus)
                VALUES (%s, %s, %s, %s, 'pending')
            """, (order_id, item['productId'], item['quantity'], item['price']))
            
            # Update product stock
            cursor.execute("""
                UPDATE Product 
                SET stockQuantity = stockQuantity - %s
                WHERE id = %s
            """, (item['quantity'], item['productId']))
            
            # Update farmer's total sales
            cursor.execute("""
                UPDATE Farmer
                SET totalSales = totalSales + %s
                WHERE userId = %s
            """, (item['quantity'], item['farmerId']))
        
        # Insert payment record (simulating successful payment)
        cursor.execute("""
            INSERT INTO Payment (checkoutId, payerId, amount, method, status, gatewayTransactionId, paidAt, gatewayResponse)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            checkout_id,
            session['user_id'],
            checkout_info['total_amount'],
            payment_method,
            'completed',
            transaction_id,
            datetime.now(),
            '{"status": "success", "message": "Payment processed successfully"}'
        ))
        payment_id = cursor.lastrowid
        
        # Create payouts for farmers (calculate 90% of product price as farmer earning)
        farmer_earnings = {}
        for item in cart_items:
            farmer_id_user = item['farmerId']
            earning = item['price'] * item['quantity'] * 0.9  # 90% goes to farmer
            
            if farmer_id_user not in farmer_earnings:
                farmer_earnings[farmer_id_user] = 0
            farmer_earnings[farmer_id_user] += earning
        
        # Insert payout records
        for farmer_user_id, amount in farmer_earnings.items():
            # Get farmer ID from userId
            cursor.execute("SELECT id FROM Farmer WHERE userId = %s", (farmer_user_id,))
            farmer_record = cursor.fetchone()
            if farmer_record:
                cursor.execute("""
                    INSERT INTO Payout (farmerId, amount, status)
                    VALUES (%s, %s, 'pending')
                """, (farmer_record['id'], amount))
        
        # Clear cart
        cursor.execute("DELETE FROM Cart WHERE userId = %s", (session['user_id'],))
        
        db.commit()
        
        # Store payment details for success page
        session['payment_success'] = {
            'order_id': order_id,
            'transaction_id': transaction_id,
            'payment_method': payment_method,
            'amount': checkout_info['total_amount']
        }
        
        # Clear pending checkout
        session.pop('pending_checkout', None)
        
        cursor.close()
        db.close()
        
        return redirect(url_for('payment_success'))
        
    except Exception as e:
        db.rollback()
        cursor.close()
        db.close()
        flash(f'Payment failed: {str(e)}', 'error')
        return redirect(url_for('payment_page'))

@app.route('/buyer/payment/success')
@buyer_required
def payment_success():
    if 'payment_success' not in session:
        flash('No payment information found', 'error')
        return redirect(url_for('buyer_dashboard'))
    
    payment_info = session['payment_success']
    
    # Clear payment success data from session after displaying
    session.pop('payment_success', None)
    
    return render_template('payment_success.html',
                         order_id=payment_info['order_id'],
                         transaction_id=payment_info['transaction_id'],
                         payment_method=payment_info['payment_method'],
                         amount=payment_info['amount'])

@app.route('/buyer/orders')
@buyer_required
def buyer_orders():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    # Get orders with item-level delivery status
    cursor.execute("""
        SELECT 
            o.id as order_id,
            o.createdAt as order_date,
            o.totalAmount,
            o.deliveryAddress,
            oi.id as order_item_id,
            oi.quantity,
            oi.price,
            oi.deliveryStatus,
            oi.deliveredAt,
            p.name as product_name,
            u.name as farmer_name
        FROM `Order` o
        JOIN OrderItem oi ON o.id = oi.orderId
        JOIN Product p ON oi.productId = p.id
        JOIN User u ON p.farmerId = u.id
        WHERE o.userId = %s
        ORDER BY o.createdAt DESC, oi.id ASC
    """, (session['user_id'],))
    
    order_items = cursor.fetchall()
    
    # Group items by order for display
    orders = {}
    for item in order_items:
        order_id = item['order_id']
        if order_id not in orders:
            orders[order_id] = {
                'id': order_id,
                'order_date': item['order_date'],
                'totalAmount': item['totalAmount'],
                'deliveryAddress': item['deliveryAddress'],
                'order_items': []  # Changed from 'items' to 'order_items'
            }
        orders[order_id]['order_items'].append(item)  # Changed from 'items' to 'order_items'
    
    cursor.close()
    db.close()
    
    return render_template('buyer_orders.html', orders=list(orders.values()))

@app.route('/buyer/review/<int:product_id>', methods=['POST'])
@buyer_required
def add_review(product_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    # Check if buyer already reviewed this product
    cursor.execute("""
        SELECT * FROM Review 
        WHERE reviewerId = %s AND productId = %s
    """, (session['user_id'], product_id))
    
    existing_review = cursor.fetchone()
    if existing_review:
        cursor.close()
        db.close()
        flash('You have already reviewed this product', 'error')
        return redirect(url_for('product_reviews', product_id=product_id))
    
    # Validate rating
    rating_raw = request.form.get('rating')
    try:
        rating = int(rating_raw)
        if rating < 1 or rating > 5:
            raise ValueError()
    except (TypeError, ValueError):
        cursor.close()
        db.close()
        flash('Invalid rating value', 'error')
        return redirect(url_for('product_reviews', product_id=product_id))

    title = request.form.get('title', '')
    comment = request.form.get('comment', '')
    order_id = request.form.get('order_id', None)

    # Verify the buyer has purchased this product
    cursor.execute("""
        SELECT oi.* FROM OrderItem oi
        JOIN `Order` o ON o.id = oi.orderId
        WHERE oi.productId = %s AND o.userId = %s
        LIMIT 1
    """, (product_id, session['user_id']))

    purchase = cursor.fetchone()
    is_verified = purchase is not None
    
    if order_id and purchase:
        # Use the provided order_id if valid
        cursor.execute("""
            SELECT * FROM OrderItem 
            WHERE orderId = %s AND productId = %s
        """, (order_id, product_id))
        if cursor.fetchone():
            order_id_to_use = order_id
        else:
            order_id_to_use = purchase['orderId']
    elif purchase:
        order_id_to_use = purchase['orderId']
    else:
        order_id_to_use = None

    # Insert review
    cursor.execute("""
        INSERT INTO Review (reviewerId, productId, orderId, rating, title, comment, isVerifiedPurchase)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (session['user_id'], product_id, order_id_to_use, rating, title, comment, is_verified))

    db.commit()
    
    # Update product average rating
    update_product_rating(product_id)
    
    cursor.close()
    db.close()

    flash('Review submitted successfully!', 'success')
    return redirect(url_for('product_reviews', product_id=product_id))

@app.route('/product/<int:product_id>/reviews')
@login_required
def product_reviews(product_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    # Get product info
    cursor.execute("""
        SELECT p.*, u.name as farmer_name
        FROM Product p
        JOIN User u ON p.farmerId = u.id
        WHERE p.id = %s
    """, (product_id,))
    product = cursor.fetchone()
    
    if not product:
        flash('Product not found', 'error')
        cursor.close()
        db.close()
        return redirect(url_for('index'))
    
    # Get all reviews for this product
    cursor.execute("""
        SELECT r.*, u.name as reviewer_name
        FROM Review r
        JOIN User u ON r.reviewerId = u.id
        WHERE r.productId = %s
        ORDER BY r.createdAt DESC
    """, (product_id,))
    reviews = cursor.fetchall()
    
    # Calculate rating statistics
    cursor.execute("""
        SELECT 
            COUNT(*) as total_reviews,
            AVG(rating) as avg_rating,
            SUM(CASE WHEN rating = 5 THEN 1 ELSE 0 END) as five_star,
            SUM(CASE WHEN rating = 4 THEN 1 ELSE 0 END) as four_star,
            SUM(CASE WHEN rating = 3 THEN 1 ELSE 0 END) as three_star,
            SUM(CASE WHEN rating = 2 THEN 1 ELSE 0 END) as two_star,
            SUM(CASE WHEN rating = 1 THEN 1 ELSE 0 END) as one_star
        FROM Review
        WHERE productId = %s
    """, (product_id,))
    stats = cursor.fetchone()
    
    # Check if current user can review (for buyers only)
    can_review = False
    has_purchased = False
    already_reviewed = False
    
    if session.get('role') == 'BUYER':
        # Check if buyer has purchased this product
        cursor.execute("""
            SELECT COUNT(*) as count FROM OrderItem oi
            JOIN `Order` o ON o.id = oi.orderId
            WHERE oi.productId = %s AND o.userId = %s
        """, (product_id, session['user_id']))
        purchase_check = cursor.fetchone()
        has_purchased = purchase_check['count'] > 0
        
        # Check if buyer already reviewed this product
        cursor.execute("""
            SELECT COUNT(*) as count FROM Review
            WHERE productId = %s AND reviewerId = %s
        """, (product_id, session['user_id']))
        review_check = cursor.fetchone()
        already_reviewed = review_check['count'] > 0
        
        can_review = has_purchased and not already_reviewed
    
    cursor.close()
    db.close()
    
    return render_template('product_reviews.html', 
                         product=product, 
                         reviews=reviews, 
                         stats=stats,
                         can_review=can_review,
                         has_purchased=has_purchased,
                         already_reviewed=already_reviewed)

if __name__ == '__main__':
    app.run(debug=True)