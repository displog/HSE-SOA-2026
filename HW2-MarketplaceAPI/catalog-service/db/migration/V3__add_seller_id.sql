-- V3: Add seller_id to products
ALTER TABLE products ADD COLUMN seller_id UUID NULL;
ALTER TABLE products ADD CONSTRAINT fk_products_seller_id
    FOREIGN KEY (seller_id) REFERENCES users(id);
