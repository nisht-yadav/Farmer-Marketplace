-- ============================
-- Create Database and Use
-- ============================

CREATE DATABASE marketplacedb2;
USE marketplacedb2;


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

