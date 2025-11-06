// OpenTelemetry instrumentation must be initialized first
const { NodeSDK } = require('@opentelemetry/sdk-node');
const { getNodeAutoInstrumentations } = require('@opentelemetry/auto-instrumentations-node');

// Initialize OpenTelemetry with environment variables
const sdk = new NodeSDK({
  instrumentations: [getNodeAutoInstrumentations({
    '@opentelemetry/instrumentation-fs': {
      enabled: false,
    },
  })],
});

sdk.start();
console.log('OpenTelemetry initialized for fabrik-orders');

// Application code
const express = require('express');
const mysql = require('mysql2/promise');
const amqp = require('amqplib');
const { v4: uuidv4 } = require('uuid');
const { trace, context } = require('@opentelemetry/api');

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
  const tracer = trace.getTracer('fabrik-orders-init');
  const span = tracer.startSpan('database_initialization');

  try {
    span.setAttributes({
      'db.system': 'mysql',
      'db.name': MYSQL_DATABASE,
      'db.operation': 'create_tables'
    });

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
    span.setStatus({ code: 1 }); // OK
  } catch (error) {
    span.recordException(error);
    span.setStatus({ code: 2, message: error.message }); // ERROR
    console.error('Failed to initialize database:', error);
  } finally {
    span.end();
  }
}

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    service: 'fabrik-orders',
    instrumentation: 'opentelemetry',
    timestamp: new Date().toISOString()
  });
});

// Create order endpoint
app.post('/orders', async (req, res) => {
  const tracer = trace.getTracer('fabrik-orders');
  const span = tracer.startSpan('create_order');

  try {
    span.setAttributes({
      'http.method': req.method,
      'http.route': '/orders',
      'http.url': req.originalUrl
    });

    // Simulate intermittent errors (every few minutes, ~5% chance)
    if (Math.random() < 0.05) {
      span.setStatus({ code: 2, message: 'Simulated order processing error' });
      span.end();
      return res.status(500).json({
        error: 'Order processing temporarily unavailable',
        service: 'fabrik-orders',
        instrumentation: 'opentelemetry'
      });
    }

    const orderId = uuidv4();
    const { customer_name, product_name, quantity, unit_price } = req.body;

    if (!customer_name || !product_name || !quantity || !unit_price) {
      span.setStatus({ code: 2, message: 'Missing required fields' });
      span.end();
      return res.status(400).json({ error: 'Missing required fields' });
    }

    const totalAmount = quantity * unit_price;

    span.setAttributes({
      'order.id': orderId,
      'order.customer': customer_name,
      'order.product': product_name,
      'order.quantity': quantity,
      'order.total': totalAmount
    });

    // Insert order into database
    const insertSpan = tracer.startSpan('database_insert', { parent: span });
    insertSpan.setAttributes({
      'db.system': 'mysql',
      'db.name': MYSQL_DATABASE,
      'db.operation': 'insert',
      'db.sql.table': 'orders'
    });

    try {
      await dbPool.execute(
        'INSERT INTO orders (id, customer_name, product_name, quantity, total_amount) VALUES (?, ?, ?, ?, ?)',
        [orderId, customer_name, product_name, quantity, totalAmount]
      );
      insertSpan.setStatus({ code: 1 });
    } catch (dbError) {
      insertSpan.recordException(dbError);
      insertSpan.setStatus({ code: 2, message: dbError.message });
      throw dbError;
    } finally {
      insertSpan.end();
    }

    // Publish to RabbitMQ for fulfillment
    if (rabbitChannel) {
      const publishSpan = tracer.startSpan('message_publish', { parent: span });
      publishSpan.setAttributes({
        'messaging.system': 'rabbitmq',
        'messaging.destination.name': QUEUE_NAME,
        'messaging.operation': 'publish'
      });

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

        publishSpan.setAttributes({
          'messaging.message.id': orderId,
          'messaging.message.payload_size_bytes': JSON.stringify(message).length
        });
        publishSpan.setStatus({ code: 1 });
        console.log('Order published to fulfillment queue:', orderId);
      } catch (mqError) {
        publishSpan.recordException(mqError);
        publishSpan.setStatus({ code: 2, message: mqError.message });
        console.error('Failed to publish to RabbitMQ:', mqError);
      } finally {
        publishSpan.end();
      }
    }

    span.setStatus({ code: 1 });
    res.status(201).json({
      message: 'Order created successfully',
      orderId,
      status: 'pending',
      service: 'fabrik-orders',
      instrumentation: 'opentelemetry'
    });

  } catch (error) {
    span.recordException(error);
    span.setStatus({ code: 2, message: error.message });
    console.error('Error creating order:', error);
    res.status(500).json({
      error: 'Failed to create order',
      service: 'fabrik-orders',
      instrumentation: 'opentelemetry'
    });
  } finally {
    span.end();
  }
});

// Get orders endpoint
app.get('/orders', async (req, res) => {
  const tracer = trace.getTracer('fabrik-orders');
  const span = tracer.startSpan('get_orders');

  try {
    span.setAttributes({
      'http.method': req.method,
      'http.route': '/orders',
      'db.system': 'mysql',
      'db.operation': 'select'
    });

    const [rows] = await dbPool.execute('SELECT * FROM orders ORDER BY created_at DESC LIMIT 20');

    span.setAttributes({
      'db.rows_affected': rows.length
    });

    span.setStatus({ code: 1 });
    res.json({
      orders: rows,
      count: rows.length,
      service: 'fabrik-orders',
      instrumentation: 'opentelemetry'
    });
  } catch (error) {
    span.recordException(error);
    span.setStatus({ code: 2, message: error.message });
    console.error('Error fetching orders:', error);
    res.status(500).json({
      error: 'Failed to fetch orders',
      service: 'fabrik-orders',
      instrumentation: 'opentelemetry'
    });
  } finally {
    span.end();
  }
});

// Get order by ID
app.get('/orders/:id', async (req, res) => {
  const tracer = trace.getTracer('fabrik-orders');
  const span = tracer.startSpan('get_order_by_id');

  try {
    const { id } = req.params;

    span.setAttributes({
      'http.method': req.method,
      'http.route': '/orders/:id',
      'order.id': id,
      'db.system': 'mysql',
      'db.operation': 'select'
    });

    const [rows] = await dbPool.execute('SELECT * FROM orders WHERE id = ?', [id]);

    if (rows.length === 0) {
      span.setStatus({ code: 1 });
      return res.status(404).json({
        error: 'Order not found',
        service: 'fabrik-orders',
        instrumentation: 'opentelemetry'
      });
    }

    span.setStatus({ code: 1 });
    res.json({
      order: rows[0],
      service: 'fabrik-orders',
      instrumentation: 'opentelemetry'
    });
  } catch (error) {
    span.recordException(error);
    span.setStatus({ code: 2, message: error.message });
    console.error('Error fetching order:', error);
    res.status(500).json({
      error: 'Failed to fetch order',
      service: 'fabrik-orders',
      instrumentation: 'opentelemetry'
    });
  } finally {
    span.end();
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
    console.log(`Fabrik Orders service (OpenTelemetry) listening on port ${port}`);
    console.log('Environment:', {
      mysql: `${MYSQL_HOST}:${MYSQL_PORT}`,
      database: MYSQL_DATABASE,
      rabbitmq: RABBITMQ_URL
    });
  });
}

startServer().catch(console.error);