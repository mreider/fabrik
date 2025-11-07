// OpenTelemetry instrumentation must be initialized first
const { NodeSDK } = require('@opentelemetry/sdk-node');
const { getNodeAutoInstrumentations } = require('@opentelemetry/auto-instrumentations-node');
// Structured logging function that will be captured by OpenTelemetry
function logEvent(level, message, attributes = {}) {
  const logEntry = {
    timestamp: new Date().toISOString(),
    level: level,
    message: message,
    service: process.env.OTEL_SERVICE_NAME || 'fabrik-fulfillment-otel',
    version: process.env.OTEL_SERVICE_VERSION || '1.0.0',
    namespace: process.env.OTEL_SERVICE_NAMESPACE || 'fabrik',
    ...attributes
  };
  console.log(`[OTEL-LOG] ${JSON.stringify(logEntry)}`);
}

// Initialize OpenTelemetry with environment variables
const sdk = new NodeSDK({
  instrumentations: [getNodeAutoInstrumentations({
    '@opentelemetry/instrumentation-fs': {
      enabled: false,
    },
  })],
});

sdk.start();
console.log('OpenTelemetry initialized for fabrik-fulfillment with logs export');

// Application code
const express = require('express');
const mysql = require('mysql2/promise');
const amqp = require('amqplib');
const { trace } = require('@opentelemetry/api');

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
  const tracer = trace.getTracer('fabrik-fulfillment');
  const span = tracer.startSpan('process_order_fulfillment');

  try {
    span.setAttributes({
      'messaging.operation': 'process',
      'messaging.system': 'rabbitmq',
      'messaging.source_queue': QUEUE_NAME,
      'order.id': orderData.orderId,
      'order.customer': orderData.customer_name,
      'order.product': orderData.product_name
    });

    console.log('Processing order fulfillment:', orderData.orderId);
    logEvent('INFO', `Processing order fulfillment: ${orderData.orderId}`, {
      'order.id': orderData.orderId,
      'order.customer': orderData.customer_name,
      'order.product': orderData.product_name,
      'order.quantity': orderData.quantity,
      'fulfillment.operation': 'process',
    });

    // Simulate intermittent processing errors (~3% chance)
    if (Math.random() < 0.03) {
      const error = new Error('Fulfillment processing failed - warehouse system unavailable');
      span.recordException(error);
      span.setStatus({ code: 2, message: error.message });
      console.error('Fulfillment error for order:', orderData.orderId, error.message);

      // Update order status to failed
      const failSpan = tracer.startSpan('database_update_failed', { parent: span });
      try {
        await dbPool.execute(
          'UPDATE orders SET status = ?, updated_at = NOW() WHERE id = ?',
          ['failed', orderData.orderId]
        );
        failSpan.setStatus({ code: 1 });
      } catch (dbError) {
        failSpan.recordException(dbError);
        failSpan.setStatus({ code: 2, message: dbError.message });
      } finally {
        failSpan.end();
      }

      throw error;
    }

    // Simulate processing time
    await new Promise(resolve => setTimeout(resolve, Math.random() * 2000 + 500));

    // Update order status to fulfilled
    const updateSpan = tracer.startSpan('database_update_fulfilled', { parent: span });
    updateSpan.setAttributes({
      'db.system': 'mysql',
      'db.name': MYSQL_DATABASE,
      'db.operation': 'update',
      'db.sql.table': 'orders'
    });

    try {
      const [result] = await dbPool.execute(
        'UPDATE orders SET status = ?, updated_at = NOW() WHERE id = ?',
        ['fulfilled', orderData.orderId]
      );

      updateSpan.setAttributes({
        'db.rows_affected': result.affectedRows
      });

      if (result.affectedRows === 0) {
        throw new Error(`Order ${orderData.orderId} not found in database`);
      }

      updateSpan.setStatus({ code: 1 });
      console.log('Order fulfilled successfully:', orderData.orderId);
      logEvent('INFO', `Order fulfilled successfully: ${orderData.orderId}`, {
        'order.id': orderData.orderId,
        'order.status': 'fulfilled',
        'fulfillment.operation': 'complete',
        'db.system': 'mysql',
      });
    } catch (dbError) {
      updateSpan.recordException(dbError);
      updateSpan.setStatus({ code: 2, message: dbError.message });
      throw dbError;
    } finally {
      updateSpan.end();
    }

    span.setStatus({ code: 1 });

  } catch (error) {
    span.recordException(error);
    span.setStatus({ code: 2, message: error.message });
    console.error('Error processing fulfillment:', error);
    throw error;
  } finally {
    span.end();
  }
}

async function startRabbitMQConsumer() {
  const tracer = trace.getTracer('fabrik-fulfillment');

  try {
    console.log('Connecting to RabbitMQ...');
    rabbitConnection = await amqp.connect(RABBITMQ_URL);
    rabbitChannel = await rabbitConnection.createChannel();

    await rabbitChannel.assertQueue(QUEUE_NAME, { durable: true });
    await rabbitChannel.prefetch(1); // Process one message at a time

    console.log('Waiting for messages in queue:', QUEUE_NAME);

    rabbitChannel.consume(QUEUE_NAME, async (message) => {
      const consumeSpan = tracer.startSpan('message_consume');

      try {
        if (message) {
          const orderData = JSON.parse(message.content.toString());

          consumeSpan.setAttributes({
            'messaging.operation': 'receive',
            'messaging.system': 'rabbitmq',
            'messaging.destination.name': QUEUE_NAME,
            'messaging.message.id': orderData.orderId,
            'messaging.message.payload_size_bytes': message.content.length
          });

          console.log('Received order for fulfillment:', orderData);

          await processOrderFulfillment(orderData);

          // Acknowledge the message
          rabbitChannel.ack(message);
          consumeSpan.setStatus({ code: 1 });
        }
      } catch (error) {
        consumeSpan.recordException(error);
        consumeSpan.setStatus({ code: 2, message: error.message });
        console.error('Error processing message:', error);

        // Reject and requeue the message for retry
        if (message) {
          rabbitChannel.nack(message, false, true);
        }
      } finally {
        consumeSpan.end();
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
    instrumentation: 'opentelemetry',
    timestamp: new Date().toISOString(),
    consumer_active: !!rabbitChannel
  });
});

// Get fulfillment stats endpoint
app.get('/stats', async (req, res) => {
  const tracer = trace.getTracer('fabrik-fulfillment');
  const span = tracer.startSpan('get_fulfillment_stats');

  try {
    span.setAttributes({
      'http.method': req.method,
      'http.route': '/stats',
      'db.system': 'mysql',
      'db.operation': 'select'
    });

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
      instrumentation: 'opentelemetry'
    };

    span.setStatus({ code: 1 });
    res.json(stats);
  } catch (error) {
    span.recordException(error);
    span.setStatus({ code: 2, message: error.message });
    console.error('Error fetching stats:', error);
    res.status(500).json({
      error: 'Failed to fetch stats',
      service: 'fabrik-fulfillment',
      instrumentation: 'opentelemetry'
    });
  } finally {
    span.end();
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
    console.log(`Fabrik Fulfillment service (OpenTelemetry) listening on port ${port}`);
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