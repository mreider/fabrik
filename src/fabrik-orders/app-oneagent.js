// Pure Node.js application for OneAgent instrumentation
// No OpenTelemetry dependencies - relies on OneAgent for instrumentation

const express = require('express');
const mysql = require('mysql2/promise');
const amqp = require('amqplib');
const { v4: uuidv4 } = require('uuid');

const app = express();
const port = process.env.PORT || 3000;

// Environment configuration
const MYSQL_HOST = process.env.MYSQL_HOST || 'mysql';
const MYSQL_PORT = process.env.MYSQL_PORT || 3306;
const MYSQL_USER = process.env.MYSQL_USER || 'fabrik';
const MYSQL_PASSWORD = process.env.MYSQL_PASSWORD || 'fabrik123';
const MYSQL_DATABASE = process.env.MYSQL_DATABASE || 'fabrik';
const RABBITMQ_URL = process.env.RABBITMQ_URL || 'amqp://fabrik:fabrik123@rabbitmq:5672';

app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// MySQL connection pool
const dbPool = mysql.createPool({
  host: MYSQL_HOST,
  port: MYSQL_PORT,
  user: MYSQL_USER,
  password: MYSQL_PASSWORD,
  database: MYSQL_DATABASE,
  waitForConnections: true,
  connectionLimit: 10,
  queueLimit: 0,
  acquireTimeout: 30000,
  timeout: 30000
});

// RabbitMQ connection
let rabbitChannel = null;
const QUEUE_NAME = 'order_fulfillment';

async function initializeRabbitMQ() {
  try {
    const connection = await amqp.connect(RABBITMQ_URL);
    rabbitChannel = await connection.createChannel();
    await rabbitChannel.assertQueue(QUEUE_NAME, { durable: true });
    console.log('RabbitMQ connected and queue created');
  } catch (error) {
    console.error('Failed to initialize RabbitMQ:', error);
    setTimeout(initializeRabbitMQ, 5000); // Retry after 5 seconds
  }
}

// Initialize database tables
async function initializeDatabase() {
  try {
    // Create orders table
    await dbPool.execute(`
      CREATE TABLE IF NOT EXISTS orders (
        id VARCHAR(36) PRIMARY KEY,
        customer_name VARCHAR(255) NOT NULL,
        product_name VARCHAR(255) NOT NULL,
        quantity INT NOT NULL,
        total_amount DECIMAL(10,2) NOT NULL,
        status ENUM('pending', 'fulfilled', 'failed') DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
      )
    `);

    console.log('Database tables initialized');
  } catch (error) {
    console.error('Failed to initialize database:', error);
  }
}

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    service: 'fabrik-orders',
    instrumentation: 'oneagent',
    timestamp: new Date().toISOString()
  });
});

// Create order endpoint
app.post('/orders', async (req, res) => {
  try {
    // Simulate intermittent errors (every few minutes, ~5% chance)
    if (Math.random() < 0.05) {
      console.error('Simulated order processing error');
      return res.status(500).json({
        error: 'Order processing temporarily unavailable',
        service: 'fabrik-orders',
        instrumentation: 'oneagent'
      });
    }

    const orderId = uuidv4();
    const { customer_name, product_name, quantity, unit_price } = req.body;

    if (!customer_name || !product_name || !quantity || !unit_price) {
      return res.status(400).json({
        error: 'Missing required fields',
        service: 'fabrik-orders',
        instrumentation: 'oneagent'
      });
    }

    const totalAmount = quantity * unit_price;

    console.log('Creating order:', {
      orderId,
      customer: customer_name,
      product: product_name,
      quantity,
      total: totalAmount
    });

    // Insert order into database
    await dbPool.execute(
      'INSERT INTO orders (id, customer_name, product_name, quantity, total_amount) VALUES (?, ?, ?, ?, ?)',
      [orderId, customer_name, product_name, quantity, totalAmount]
    );

    // Publish to RabbitMQ for fulfillment
    if (rabbitChannel) {
      try {
        const message = {
          orderId,
          customer_name,
          product_name,
          quantity,
          total_amount: totalAmount,
          created_at: new Date().toISOString()
        };

        await rabbitChannel.sendToQueue(QUEUE_NAME, Buffer.from(JSON.stringify(message)), {
          persistent: true
        });

        console.log('Order published to fulfillment queue:', orderId);
      } catch (mqError) {
        console.error('Failed to publish to RabbitMQ:', mqError);
      }
    }

    res.status(201).json({
      message: 'Order created successfully',
      orderId,
      status: 'pending',
      service: 'fabrik-orders',
      instrumentation: 'oneagent'
    });

  } catch (error) {
    console.error('Error creating order:', error);
    res.status(500).json({
      error: 'Failed to create order',
      service: 'fabrik-orders',
      instrumentation: 'oneagent'
    });
  }
});

// Get orders endpoint
app.get('/orders', async (req, res) => {
  try {
    const [rows] = await dbPool.execute('SELECT * FROM orders ORDER BY created_at DESC LIMIT 20');

    res.json({
      orders: rows,
      count: rows.length,
      service: 'fabrik-orders',
      instrumentation: 'oneagent'
    });
  } catch (error) {
    console.error('Error fetching orders:', error);
    res.status(500).json({
      error: 'Failed to fetch orders',
      service: 'fabrik-orders',
      instrumentation: 'oneagent'
    });
  }
});

// Get order by ID
app.get('/orders/:id', async (req, res) => {
  try {
    const { id } = req.params;

    const [rows] = await dbPool.execute('SELECT * FROM orders WHERE id = ?', [id]);

    if (rows.length === 0) {
      return res.status(404).json({
        error: 'Order not found',
        service: 'fabrik-orders',
        instrumentation: 'oneagent'
      });
    }

    res.json({
      order: rows[0],
      service: 'fabrik-orders',
      instrumentation: 'oneagent'
    });
  } catch (error) {
    console.error('Error fetching order:', error);
    res.status(500).json({
      error: 'Failed to fetch order',
      service: 'fabrik-orders',
      instrumentation: 'oneagent'
    });
  }
});

// Graceful shutdown
process.on('SIGTERM', async () => {
  console.log('Received SIGTERM, shutting down gracefully');
  await dbPool.end();
  process.exit(0);
});

// Initialize and start server
async function startServer() {
  await initializeDatabase();
  await initializeRabbitMQ();

  app.listen(port, () => {
    console.log(`Fabrik Orders service (OneAgent) listening on port ${port}`);
    console.log('Environment:', {
      mysql: `${MYSQL_HOST}:${MYSQL_PORT}`,
      database: MYSQL_DATABASE,
      rabbitmq: RABBITMQ_URL
    });
  });
}

startServer().catch(console.error);