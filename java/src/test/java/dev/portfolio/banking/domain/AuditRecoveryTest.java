package dev.portfolio.banking.domain;
import dev.portfolio.banking.infrastructure.AuditEvent;
import dev.portfolio.banking.application.OutboxStatus;
import tools.jackson.databind.json.JsonMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.NullSource;
import org.junit.jupiter.params.provider.ValueSource;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;
import static org.junit.jupiter.api.Assertions.*;

class AuditRecoveryTest {
    Map<String, Object> event() {
        var value = new LinkedHashMap<String, Object>();
        for (var field : new String[]{"eventId", "transferId", "sourceId", "destinationId"}) value.put(field, UUID.randomUUID().toString());
        value.put("schemaVersion", 1); value.put("type", "TransferCompleted"); value.put("amountMinor", 100L); value.put("currency", "USD");
        return value;
    }
    @Test void validEventPreservesIdentityAndMinorUnits() {
        var value = event(); var parsed = AuditEvent.parse(JsonMapper.builder().build().writeValueAsString(value));
        assertEquals(value.get("eventId"), parsed.eventId().toString()); assertEquals(100L, parsed.amountMinor());
    }
    @Test void poisonValuesRejected() {
        Object[][] cases = {{"amountMinor", "100"}, {"amountMinor", 1.5}, {"amountMinor", 0}, {"amountMinor", -1}, {"amountMinor", 9000000000001L},
            {"currency", "BTC"}, {"currency", null}, {"schemaVersion", "1"}, {"schemaVersion", 2}, {"eventId", "bad-uuid"},
            {"eventId", "00000000-0000-0000-0000-000000000000"}, {"eventId", null}, {"extra", true}};
        for (var item : cases) {
            var message = event(); message.put((String)item[0], item[1]);
            assertThrows(AuditEvent.Invalid.class, () -> AuditEvent.parse(JsonMapper.builder().build().writeValueAsString(message)), (String)item[0]);
        }
    }
    @ParameterizedTest @NullSource @ValueSource(strings={"{", "[]", "null", "{}"})
    void invalidJsonAndShapeRejected(String raw) { assertThrows(AuditEvent.Invalid.class, () -> AuditEvent.parse(raw)); }
    @Test void duplicateFieldsAndSameAccountRejected() {
        var value = event(); var raw = JsonMapper.builder().build().writeValueAsString(value);
        assertThrows(AuditEvent.Invalid.class, () -> AuditEvent.parse(raw.substring(0, raw.length()-1) + ",\"currency\":\"USD\"}"));
        assertThrows(AuditEvent.Invalid.class, () -> AuditEvent.parse(raw + " {}"));
        value.put("destinationId", value.get("sourceId"));
        assertThrows(AuditEvent.Invalid.class, () -> AuditEvent.parse(JsonMapper.builder().build().writeValueAsString(value)));
    }
    @Test void ageAlertHasInclusiveThreshold() {
        assertEquals(new OutboxStatus(0, 0, 60, false), OutboxStatus.assess(0, 120, 60));
        assertFalse(OutboxStatus.assess(1, 59, 60).alert()); assertTrue(OutboxStatus.assess(2, 60, 60).alert());
        assertThrows(IllegalArgumentException.class, () -> OutboxStatus.assess(1, 0, 0));
        assertThrows(IllegalArgumentException.class, () -> OutboxStatus.assess(1, 0, 86401));
    }
}
