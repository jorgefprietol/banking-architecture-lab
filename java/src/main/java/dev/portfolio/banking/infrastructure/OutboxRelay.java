package dev.portfolio.banking.infrastructure;

import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.common.serialization.StringSerializer;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

@Component
public final class OutboxRelay implements AutoCloseable {
    private final JdbcTemplate db;
    private final TransactionTemplate transaction;
    private final KafkaProducer<String, String> producer;
    private final String topic;
    record Pending(UUID id, UUID aggregate, String payload) {}
    public OutboxRelay(JdbcTemplate db, PlatformTransactionManager tx, @Value("${KAFKA_BOOTSTRAP}") String bootstrap, @Value("${KAFKA_TOPIC}") String topic) {
        this.db = db; this.transaction = new TransactionTemplate(tx); this.topic = topic;
        producer = new KafkaProducer<>(Map.of("bootstrap.servers", bootstrap, "enable.idempotence", true,
            "acks", "all", "delivery.timeout.ms", 5000, "request.timeout.ms", 3000,
            "max.block.ms", 5000), new StringSerializer(), new StringSerializer());
    }
    @Scheduled(fixedDelay=500)
    public void relay() {
        try {
            transaction.executeWithoutResult(status -> {
                var rows = db.query("SELECT event_id,aggregate_id,payload::text FROM outbox WHERE published_at IS NULL ORDER BY created_at LIMIT 50 FOR UPDATE SKIP LOCKED",
                    (rs, row) -> new Pending(rs.getObject("event_id", UUID.class), rs.getObject("aggregate_id", UUID.class), rs.getString("payload")));
                for (var item : rows) {
                    try { producer.send(new ProducerRecord<>(topic, item.aggregate().toString(), item.payload())).get(6, TimeUnit.SECONDS); }
                    catch (Exception ex) { throw new IllegalStateException("delivery_deferred", ex); }
                    db.update("UPDATE outbox SET published_at=now() WHERE event_id=?", item.id());
                }
            });
        } catch (RuntimeException ex) { LoggerFactory.getLogger(getClass()).warn("Outbox delivery deferred", ex); }
    }
    public void close() { producer.close(); }
}
