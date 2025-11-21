-- ============================
-- Create Database and Use
-- ============================

CREATE DATABASE marketplacedb;
USE marketplacedb;

-- ============================
-- ENUMS
-- ============================

-- ============================
-- TABLES
-- ============================

CREATE TABLE User (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    phone VARCHAR(50),
    location VARCHAR(255),
    role enum('BUYER','FARMER') DEFAULT 'BUYER',
    createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    updatedAt DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE Farmer (
    id INT AUTO_INCREMENT PRIMARY KEY,
    userId INT UNIQUE,
    farmName VARCHAR(255) DEFAULT 'My Farm',
    rating FLOAT DEFAULT 0,
    totalSales INT DEFAULT 0
);

CREATE TABLE Buyer (
    id INT AUTO_INCREMENT PRIMARY KEY,
    userId INT UNIQUE,
    address TEXT
);

CREATE TABLE Product (
    id INT AUTO_INCREMENT PRIMARY KEY,
    farmerId INT NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price FLOAT NOT NULL,
    stockQuantity INT NOT NULL,
    isAvailable BOOLEAN DEFAULT TRUE,
    averageRating FLOAT DEFAULT NULL,
    createdAt DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE Cart (
    id INT AUTO_INCREMENT PRIMARY KEY,
    userId INT NOT NULL,
    productId INT NOT NULL,
    quantity INT DEFAULT 1,
    addedAt DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE Checkout (
    id INT AUTO_INCREMENT PRIMARY KEY,
    customerId INT NOT NULL,
    grandTotal FLOAT NOT NULL,
    deliveryFee FLOAT,
    createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    updatedAt DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE `Order` (
    id INT AUTO_INCREMENT PRIMARY KEY,
    userId INT NOT NULL,
    totalAmount FLOAT NOT NULL,
    deliveryAddress VARCHAR(500), -- <-- MIGRATION CHANGE APPLIED
    status VARCHAR(50) DEFAULT 'pending',
    createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    checkoutId INT
);

CREATE TABLE OrderItem (
    id INT AUTO_INCREMENT PRIMARY KEY,
    orderId INT NOT NULL,
    productId INT NOT NULL,
    quantity INT NOT NULL,
    price FLOAT NOT NULL,
    deliveryStatus ENUM('pending', 'shipped', 'delivered') DEFAULT 'pending', -- <-- MIGRATION CHANGE APPLIED
    deliveredAt DATETIME NULL -- <-- MIGRATION CHANGE APPLIED
);

CREATE TABLE Payout (
    id INT AUTO_INCREMENT PRIMARY KEY,
    farmerId INT NOT NULL,
    amount FLOAT NOT NULL,
    status ENUM('pending', 'transferred') DEFAULT 'pending', -- <-- MIGRATION CHANGE APPLIED
    createdAt DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE Payment (
    id INT AUTO_INCREMENT PRIMARY KEY,
    checkoutId INT NOT NULL,
    payerId INT NOT NULL,
    amount FLOAT NOT NULL,
    method VARCHAR(255),
    status VARCHAR(50) DEFAULT 'pending',
    gatewayTransactionId VARCHAR(255),
    paidAt DATETIME,
    gatewayResponse JSON
);


CREATE TABLE Review (
    id INT AUTO_INCREMENT PRIMARY KEY,
    reviewerId INT NOT NULL,
    productId INT,
    orderId INT,
    rating INT,
    title VARCHAR(255),
    comment TEXT,
    isVerifiedPurchase BOOLEAN,
    createdAt DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ============================
-- CONSTRAINTS
-- ============================
ALTER TABLE Farmer
    ADD CONSTRAINT fk_farmer_user
    FOREIGN KEY (userId) REFERENCES User(id);

ALTER TABLE Buyer
    ADD CONSTRAINT fk_buyer_user
    FOREIGN KEY (userId) REFERENCES User(id);

ALTER TABLE Product
    ADD CONSTRAINT fk_product_farmer
    FOREIGN KEY (farmerId) REFERENCES Farmer(id);

ALTER TABLE Cart
    ADD CONSTRAINT fk_cart_user
    FOREIGN KEY (userId) REFERENCES User(id),
    ADD CONSTRAINT fk_cart_product
    FOREIGN KEY (productId) REFERENCES Product(id);

ALTER TABLE `Order`
    ADD CONSTRAINT fk_order_user
    FOREIGN KEY (userId) REFERENCES User(id),
    ADD CONSTRAINT fk_order_checkout
    FOREIGN KEY (checkoutId) REFERENCES Checkout(id);

ALTER TABLE OrderItem
    ADD CONSTRAINT fk_orderitem_order
    FOREIGN KEY (orderId) REFERENCES `Order`(id),
    ADD CONSTRAINT fk_orderitem_product
    FOREIGN KEY (productId) REFERENCES Product(id);

ALTER TABLE Payout
    ADD CONSTRAINT fk_payout_farmer
    FOREIGN KEY (farmerId) REFERENCES Farmer(id);

ALTER TABLE Checkout
    ADD CONSTRAINT fk_checkout_user
    FOREIGN KEY (customerId) REFERENCES User(id);

ALTER TABLE Payment
    ADD CONSTRAINT fk_payment_checkout
    FOREIGN KEY (checkoutId) REFERENCES Checkout(id),
    ADD CONSTRAINT fk_payment_payer
    FOREIGN KEY (payerId) REFERENCES User(id);


ALTER TABLE Review
    ADD CONSTRAINT fk_review_reviewer
    FOREIGN KEY (reviewerId) REFERENCES User(id),
    ADD CONSTRAINT fk_review_product
    FOREIGN KEY (productId) REFERENCES Product(id),
    ADD CONSTRAINT fk_review_order
    FOREIGN KEY (orderId) REFERENCES `Order`(id);

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
AFTER UPDATE ON Payment
FOR EACH ROW
BEGIN
    IF NEW.status = 'completed' AND OLD.status != 'completed' THEN

        INSERT INTO Payout (farmerId, amount, status)
        SELECT p.farmerId, NEW.amount, 'pending'
        FROM Checkout c
        JOIN `Order` o ON o.checkoutId = c.id
        JOIN OrderItem oi ON oi.orderId = o.id
        JOIN Product p ON p.id = oi.productId
        WHERE c.id = NEW.checkoutId
        LIMIT 1;

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