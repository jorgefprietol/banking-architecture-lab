package dev.portfolio.banking.infrastructure;

import dev.portfolio.banking.domain.Money;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.clients.consumer.OffsetAndMetadata;
import org.apache.kafka.common.TopicPartition;
import org.apache.kafka.common.serialization.StringDeserializer;
import tools.jackson.databind.json.JsonMapper;
import java.sql.DriverManager;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicBoolean;
import org.apache.kafka.common.errors.WakeupException;

public final class AuditWorker {
    private AuditWorker() {}
    static String required(String name) {
        var value = System.getenv(name);
        if (value == null) throw new IllegalStateException("Missing " + name);
        return value;
    }
    public static void run() throws Exception {
        var mapper = JsonMapper.builder().build();
        try (var connection = DriverManager.getConnection(required("AUDIT_JDBC_URL"), required("DB_USER"), required("DB_PASSWORD"));
             var consumer = new KafkaConsumer<String, String>(Map.of("bootstrap.servers", required("KAFKA_BOOTSTRAP"),
                "group.id", required("KAFKA_GROUP"), "auto.offset.reset", "earliest", "enable.auto.commit", false),
                new StringDeserializer(), new StringDeserializer())) {
            consumer.subscribe(List.of(required("KAFKA_TOPIC")));
            var closing = new AtomicBoolean();
            Runtime.getRuntime().addShutdownHook(new Thread(() -> { closing.set(true); consumer.wakeup(); }));
            try {
            while (!closing.get()) {
                for (var record : consumer.poll(Duration.ofSeconds(1))) {
                    var root = mapper.readTree(record.value());
                    if (root.get("schemaVersion").asInt() != 1 || !"TransferCompleted".equals(root.get("type").asString()))
                        throw new IllegalStateException("unsupported_event_contract");
                    var eventId = UUID.fromString(root.get("eventId").asString());
                    var transferId = UUID.fromString(root.get("transferId").asString());
                    new Money(root.get("amountMinor").asLong(), root.get("currency").asString());
                    try (var command = connection.prepareStatement("INSERT INTO inbox(event_id,transfer_id,payload) VALUES(?,?,?::jsonb) ON CONFLICT DO NOTHING")) {
                        command.setObject(1, eventId); command.setObject(2, transferId); command.setString(3, record.value()); command.executeUpdate();
                    }
                    consumer.commitSync(Map.of(new TopicPartition(record.topic(), record.partition()), new OffsetAndMetadata(record.offset() + 1)));
                }
            }
            } catch (WakeupException ex) {
                if (!closing.get()) throw ex;
            } finally {
                consumer.close(Duration.ofSeconds(5));
            }
        }
    }
}
