<img width="1892" height="922" alt="image" src="https://github.com/user-attachments/assets/c06124f2-41bb-41e5-b361-1b3b065aba0d" />

Make sure you have Python 3.8+ and MySQL installed. Then install dependencies:

pip install flask
pip install flask-mysqldb
pip install mysql-connector-python
pip install werkzeug
pip install google-generativeai


Run the following SQL commands to set up the database:

-- Create Database
CREATE DATABASE nutriscan;
USE nutriscan;

-- Users Table
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL
);

-- History Table
CREATE TABLE history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    category VARCHAR(100),
    filename VARCHAR(255),
    result TEXT,
    timestamp DATETIME,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Check history data
SELECT * FROM history;

-- Custom Requests Table
CREATE TABLE custom_requests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    prompt TEXT NOT NULL,
    filename VARCHAR(255),
    result TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Check custom requests data
SELECT * FROM custom_requests;
