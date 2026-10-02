package dev.portfolio.banking.infrastructure;

import dev.portfolio.banking.domain.Money;
import dev.portfolio.banking.domain.DomainException;
import tools.jackson.core.StreamReadFeature;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.DeserializationFeature;
import tools.jackson.databind.json.JsonMapper;
import java.util.Set;
import java.util.UUID;

public record AuditEvent(UUID eventId, UUID transferId, UUID sourceId, UUID destinationId, long amountMinor, String currency) {
    public static final class Invalid extends RuntimeException { public Invalid(String code) { super(code); } }
    private static final JsonMapper MAPPER = JsonMapper.builder().enable(StreamReadFeature.STRICT_DUPLICATE_DETECTION)
        .enable(DeserializationFeature.FAIL_ON_TRAILING_TOKENS).build();
    private static final Set<String> FIELDS = Set.of("eventId", "type", "schemaVersion", "transferId", "sourceId", "destinationId", "amountMinor", "currency");
    public static AuditEvent parse(String payload) {
        if (payload == null) throw new Invalid("invalid_event_json");
        JsonNode root;
        try { root = MAPPER.readTree(payload); }
        catch (tools.jackson.core.JacksonException ex) { throw new Invalid("invalid_event_json"); }
        if (root == null || !root.isObject() || root.size() != FIELDS.size() || !root.propertyNames().equals(FIELDS)) throw new Invalid("invalid_event_shape");
        if (!root.get("schemaVersion").isIntegralNumber() || !root.get("schemaVersion").canConvertToInt() || root.get("schemaVersion").asInt() != 1 ||
            !root.get("type").isString() || !"TransferCompleted".equals(root.get("type").asString())) throw new Invalid("unsupported_event_contract");
        var source = identity(root, "sourceId"); var destination = identity(root, "destinationId");
        if (source.equals(destination)) throw new Invalid("invalid_event_identity");
        var amount = root.get("amountMinor"); var currency = root.get("currency");
        if (!amount.isIntegralNumber() || !amount.canConvertToLong() || amount.asLong() <= 0 || !currency.isString()) throw new Invalid("invalid_event_money");
        try { new Money(amount.asLong(), currency.asString()); }
        catch (DomainException ex) { throw new Invalid("invalid_event_money"); }
        return new AuditEvent(identity(root, "eventId"), identity(root, "transferId"), source, destination, amount.asLong(), currency.asString());
    }
    private static UUID identity(JsonNode root, String name) {
        var node = root.get(name);
        if (!node.isString()) throw new Invalid("invalid_event_identity");
        try {
            var id = UUID.fromString(node.asString());
            if (!id.toString().equalsIgnoreCase(node.asString()) || id.equals(new UUID(0, 0))) throw new IllegalArgumentException();
            return id;
        } catch (IllegalArgumentException ex) { throw new Invalid("invalid_event_identity"); }
    }
}
