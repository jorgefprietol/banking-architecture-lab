package dev.portfolio.banking.infrastructure;

import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.clients.consumer.OffsetAndMetadata;
import org.apache.kafka.clients.consumer.CloseOptions;
import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.common.TopicPartition;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.apache.kafka.common.serialization.StringSerializer;
import org.apache.kafka.common.errors.WakeupException;
import org.slf4j.LoggerFactory;
import tools.jackson.databind.json.JsonMapper;
import java.sql.Connection;
import java.sql.DriverManager;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.LinkedHashMap;
import java.util.UUID;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

public final class AuditWorker {
    private AuditWorker() {}
    static String required(String name) {
        var value = System.getenv(name);
        if (value == null) throw new IllegalStateException("Missing " + name);
        return value;
    }
    private static void store(Connection connection, ConsumerRecord<String, String> record) throws Exception {
        try {
            var parsed = AuditEvent.parse(record.value());
            try (var command = connection.prepareStatement("INSERT INTO inbox(event_id,transfer_id,payload) VALUES(?,?,?::jsonb) ON CONFLICT DO NOTHING")) {
                command.setObject(1, parsed.eventId()); command.setObject(2, parsed.transferId()); command.setString(3, record.value());
                if (command.executeUpdate() == 0) {
                    try (var existing = connection.prepareStatement("SELECT payload::text FROM inbox WHERE event_id=? OR transfer_id=?")) {
                        existing.setObject(1, parsed.eventId()); existing.setObject(2, parsed.transferId());
                        try (var rows = existing.executeQuery()) {
                            var found = false;
                            while (rows.next()) {
                                found = true;
                                if (!AuditEvent.parse(rows.getString(1)).equals(parsed)) throw new AuditEvent.Invalid("event_identity_conflict");
                            }
                            if (!found) throw new IllegalStateException("inbox_conflict_without_record");
                        }
                    }
                }
            }
        } catch (AuditEvent.Invalid failure) {
            var id = UUID.randomUUID(); var envelope = new LinkedHashMap<String, Object>();
            envelope.put("schemaVersion", 1); envelope.put("type", "AuditEventRejected"); envelope.put("failureId", id.toString());
            envelope.put("sourceTopic", record.topic()); envelope.put("sourcePartition", record.partition()); envelope.put("sourceOffset", record.offset());
            envelope.put("originalKey", record.key()); envelope.put("rawPayload", record.value()); envelope.put("errorCode", failure.getMessage()); envelope.put("rejectedAt", Instant.now().toString());
            try (var command = connection.prepareStatement("INSERT INTO dead_letters(id,source_topic,source_partition,source_offset,raw_payload,error_code,payload) VALUES(?,?,?,?,?,?,?::jsonb) ON CONFLICT(source_topic,source_partition,source_offset) DO NOTHING")) {
                command.setObject(1, id); command.setString(2, record.topic()); command.setInt(3, record.partition()); command.setLong(4, record.offset());
                command.setString(5, record.value()); command.setString(6, failure.getMessage()); command.setString(7, JsonMapper.builder().build().writeValueAsString(envelope)); command.executeUpdate();
            }
            LoggerFactory.getLogger(AuditWorker.class).warn("audit_event_quarantined reason={} topic={} partition={} offset={}", failure.getMessage(), record.topic(), record.partition(), record.offset());
        }
    }
    private static void relay(Connection connection, KafkaProducer<String, String> producer, String topic) throws Exception {
        connection.setAutoCommit(false);
        try {
            try (var select = connection.prepareStatement("SELECT id,payload::text FROM dead_letters WHERE published_at IS NULL ORDER BY rejected_at LIMIT 50 FOR UPDATE SKIP LOCKED"); var rows = select.executeQuery()) {
                while (rows.next()) {
                    var id = rows.getObject(1, UUID.class);
                    producer.send(new ProducerRecord<>(topic, id.toString(), rows.getString(2))).get(6, TimeUnit.SECONDS);
                    try (var update = connection.prepareStatement("UPDATE dead_letters SET published_at=now() WHERE id=?")) { update.setObject(1, id); update.executeUpdate(); }
                }
            }
            connection.commit();
        } catch (java.util.concurrent.ExecutionException | java.util.concurrent.TimeoutException | org.apache.kafka.common.KafkaException ex) {
            connection.rollback(); LoggerFactory.getLogger(AuditWorker.class).warn("audit_dlq_delivery_deferred");
        } catch (Exception ex) { connection.rollback(); throw ex; }
        finally { connection.setAutoCommit(true); }
    }
    public static void run() throws Exception {
        try (var connection = DriverManager.getConnection(required("AUDIT_JDBC_URL"), required("DB_USER"), required("DB_PASSWORD"));
             var consumer = new KafkaConsumer<String, String>(Map.of("bootstrap.servers", required("KAFKA_BOOTSTRAP"), "group.id", required("KAFKA_GROUP"), "auto.offset.reset", "earliest", "enable.auto.commit", false), new StringDeserializer(), new StringDeserializer());
             var producer = new KafkaProducer<String, String>(Map.of("bootstrap.servers", required("KAFKA_BOOTSTRAP"), "enable.idempotence", true, "acks", "all", "delivery.timeout.ms", 5000, "request.timeout.ms", 3000, "max.block.ms", 5000), new StringSerializer(), new StringSerializer())) {
            var dlq = required("KAFKA_DLQ_TOPIC"); consumer.subscribe(List.of(required("KAFKA_TOPIC")));
            var closing = new AtomicBoolean();
            Runtime.getRuntime().addShutdownHook(new Thread(() -> { closing.set(true); consumer.wakeup(); }));
            try {
                while (!closing.get()) {
                    for (var record : consumer.poll(Duration.ofSeconds(1))) {
                        store(connection, record);
                        // Offset advances only after durable SQL storage, including quarantine.
                        consumer.commitSync(Map.of(new TopicPartition(record.topic(), record.partition()), new OffsetAndMetadata(record.offset() + 1)));
                    }
                    relay(connection, producer, dlq);
                }
            } catch (WakeupException ex) { if (!closing.get()) throw ex; }
            finally { consumer.close(CloseOptions.timeout(Duration.ofSeconds(5))); }
        }
    }
}
