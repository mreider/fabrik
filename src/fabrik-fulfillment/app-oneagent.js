// Pure Node.js application for OneAgent instrumentation
// No OpenTelemetry dependencies - relies on OneAgent for instrumentation

const express = require('express');
const mysql = require('mysql2/promise');
const amqp = require('amqplib');

const app = express();
const port = process.env.PORT || 3001;

// Environment configuration
const MYSQL_HOST = process.env.MYSQL_HOST || 'mysql';
const MYSQL_PORT = process.env.MYSQL_PORT || 3306;
const MYSQL_USER = process.env.MYSQL_USER || 'fabrik';
const MYSQL_PASSWORD = process.env.MYSQL_PASSWORD || 'fabrik123';
const MYSQL_DATABASE = process.env.MYSQL_DATABASE || 'fabrik';
const RABBITMQ_URL = process.env.RABBITMQ_URL || 'amqp://fabrik:fabrik123@rabbitmq:5672';

app.use(express.json());

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
let rabbitConnection = null;
const QUEUE_NAME = 'order_fulfillment';

async function processOrderFulfillment(orderData) {
  try {
    console.log('Processing order fulfillment:', orderData.orderId);

    // Simulate intermittent processing errors (~3% chance)
    if (Math.random() < 0.03) {
      const error = new Error('Fulfillment processing failed - warehouse system unavailable');
      console.error('Fulfillment error for order:', orderData.orderId, error.message);

      // Update order status to failed
      await dbPool.execute(
        'UPDATE orders SET status = ?, updated_at = NOW() WHERE id = ?',
        ['failed', orderData.orderId]
      );

      throw error;
    }

    // Simulate processing time
    await new Promise(resolve => setTimeout(resolve, Math.random() * 2000 + 500));

    // Update order status to fulfilled
    const [result] = await dbPool.execute(
      'UPDATE orders SET status = ?, updated_at = NOW() WHERE id = ?',
      ['fulfilled', orderData.orderId]
    );

    if (result.affectedRows === 0) {
      throw new Error(`Order ${orderData.orderId} not found in database`);
    }

    console.log('Order fulfilled successfully:', orderData.orderId);

  } catch (error) {
    console.error('Error processing fulfillment:', error);
    throw error;
  }
}

async function startRabbitMQConsumer() {
  try {
    console.log('Connecting to RabbitMQ...');
    rabbitConnection = await amqp.connect(RABBITMQ_URL);
    rabbitChannel = await rabbitConnection.createChannel();

    await rabbitChannel.assertQueue(QUEUE_NAME, { durable: true });
    await rabbitChannel.prefetch(1); // Process one message at a time

    console.log('Waiting for messages in queue:', QUEUE_NAME);

    rabbitChannel.consume(QUEUE_NAME, async (message) => {
      try {
        if (message) {
          const orderData = JSON.parse(message.content.toString());
          console.log('Received order for fulfillment:', orderData);

          await processOrderFulfillment(orderData);

          // Acknowledge the message
          rabbitChannel.ack(message);
        }
      } catch (error) {
        console.error('Error processing message:', error);

        // Reject and requeue the message for retry
        if (message) {
          rabbitChannel.nack(message, false, true);
        }
      }
    }, {
      noAck: false
    });

  } catch (error) {
    console.error('Failed to start RabbitMQ consumer:', error);
    setTimeout(startRabbitMQConsumer, 5000); // Retry after 5 seconds
  }
}

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    service: 'fabrik-fulfillment',
    instrumentation: 'oneagent',
    timestamp: new Date().toISOString(),
    consumer_active: !!rabbitChannel
  });
});

// Get fulfillment stats endpoint
app.get('/stats', async (req, res) => {
  try {
    const [rows] = await dbPool.execute(`
      SELECT
        status,
        COUNT(*) as count
      FROM orders
      GROUP BY status
    `);

    const stats = {
      total: rows.reduce((sum, row) => sum + row.count, 0),
      by_status: rows.reduce((acc, row) => {
        acc[row.status] = row.count;
        return acc;
      }, {}),
      service: 'fabrik-fulfillment',
      instrumentation: 'oneagent'
    };

    res.json(stats);
  } catch (error) {
    console.error('Error fetching stats:', error);
    res.status(500).json({
      error: 'Failed to fetch stats',
      service: 'fabrik-fulfillment',
      instrumentation: 'oneagent'
    });
  }
});

// Graceful shutdown
process.on('SIGTERM', async () => {
  console.log('Received SIGTERM, shutting down gracefully');

  if (rabbitChannel) {
    await rabbitChannel.close();
  }
  if (rabbitConnection) {
    await rabbitConnection.close();
  }
  await dbPool.end();
  process.exit(0);
});

// Start server and consumer
async function startServer() {
  // Start the HTTP server
  app.listen(port, () => {
    console.log(`Fabrik Fulfillment service (OneAgent) listening on port ${port}`);
    console.log('Environment:', {
      mysql: `${MYSQL_HOST}:${MYSQL_PORT}`,
      database: MYSQL_DATABASE,
      rabbitmq: RABBITMQ_URL
    });
  });

  // Start RabbitMQ consumer
  await startRabbitMQConsumer();
}

startServer().catch(console.error);