-- ============================
-- TRIGGERS
-- ============================

DELIMITER $$

CREATE TRIGGER update_product_rating_after_insert
AFTER INSERT ON Review
FOR EACH ROW
BEGIN
    UPDATE Product
    SET averageRating = (
        SELECT AVG(rating) FROM Review WHERE productId = NEW.productId
    )
    WHERE id = NEW.productId;
END$$

CREATE TRIGGER update_product_rating_after_update
AFTER UPDATE ON Review
FOR EACH ROW
BEGIN
    UPDATE Product
    SET averageRating = (
        SELECT AVG(rating) FROM Review WHERE productId = NEW.productId
    )
    WHERE id = NEW.productId;
END$$

CREATE TRIGGER update_product_rating_after_delete
AFTER DELETE ON Review
FOR EACH ROW
BEGIN
    UPDATE Product
    SET averageRating = (
        SELECT AVG(rating) FROM Review WHERE productId = OLD.productId
    )
    WHERE id = OLD.productId;
END$$

CREATE TRIGGER reduce_stock_after_orderitem
AFTER INSERT ON OrderItem
FOR EACH ROW
BEGIN
    UPDATE Product
    SET stockQuantity = stockQuantity - NEW.quantity
    WHERE id = NEW.productId;
END$$

CREATE TRIGGER mark_not_available_when_zero
AFTER UPDATE ON Product
FOR EACH ROW
BEGIN
    IF NEW.stockQuantity <= 0 THEN
        UPDATE Product SET isAvailable = FALSE WHERE id = NEW.id;
    END IF;
END$$

CREATE TRIGGER prevent_negative_stock
BEFORE UPDATE ON Product
FOR EACH ROW
BEGIN
    IF NEW.stockQuantity < 0 THEN
        SET NEW.stockQuantity = 0;
    END IF;
END$$

CREATE TRIGGER set_delivered_timestamp
BEFORE UPDATE ON OrderItem
FOR EACH ROW
BEGIN
    IF NEW.deliveryStatus = 'delivered' AND OLD.deliveryStatus != 'delivered' THEN
        SET NEW.deliveredAt = NOW();
    END IF;
END$$

CREATE TRIGGER update_farmer_total_sales
AFTER INSERT ON OrderItem
FOR EACH ROW
BEGIN
    DECLARE farmerId INT;

    SELECT farmerId INTO farmerId FROM Product WHERE id = NEW.productId;

    UPDATE Farmer
    SET totalSales = totalSales + NEW.quantity
    WHERE id = farmerId;
END$$

CREATE TRIGGER create_payout_after_payment
AFTER INSERT ON Payment
FOR EACH ROW
BEGIN
    -- Only proceed if payment status is 'completed'
    IF NEW.status = 'completed' THEN
        
        -- Insert a payout for EACH farmer involved in this checkout
        -- Calculate the correct amount per farmer (sum of their order items)
        INSERT INTO Payout (farmerId, amount, status)
        SELECT 
            p.farmerId,
            SUM(oi.quantity * oi.price) AS farmerTotal,
            'pending'
        FROM Checkout c
        JOIN `Order` o ON o.checkoutId = c.id
        JOIN OrderItem oi ON oi.orderId = o.id
        JOIN Product p ON p.id = oi.productId
        WHERE c.id = NEW.checkoutId
        GROUP BY p.farmerId;
        
    END IF;
END$$

CREATE TRIGGER validate_review_purchase
BEFORE INSERT ON Review
FOR EACH ROW
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM OrderItem oi
        JOIN `Order` o ON oi.orderId = o.id
        WHERE o.userId = NEW.reviewerId
        AND oi.productId = NEW.productId
    ) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Cannot review without verified purchase';
    END IF;
END$$

DELIMITER ;