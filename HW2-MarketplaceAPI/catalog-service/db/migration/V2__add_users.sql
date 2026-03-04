-- V2: Users table
CREATE TABLE users (
    id UUID NOT NULL DEFAULT uuid_generate_v4(),
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'USER',
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('UTC', now()),
    PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_users_email ON users (email);
