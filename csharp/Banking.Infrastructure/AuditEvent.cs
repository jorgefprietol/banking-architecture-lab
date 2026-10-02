using System.Text.Json;
using Banking.Domain;
namespace Banking.Infrastructure;

public sealed class InvalidAuditEvent(string code) : Exception(code);
public sealed record AuditEvent(Guid EventId, Guid TransferId, Guid SourceId, Guid DestinationId, long AmountMinor, string Currency)
{
    private static readonly HashSet<string> Fields = ["eventId", "type", "schemaVersion", "transferId", "sourceId", "destinationId", "amountMinor", "currency"];
    public static AuditEvent Parse(string? payload)
    {
        if (payload is null) throw new InvalidAuditEvent("invalid_event_json");
        JsonDocument json;
        try { json = JsonDocument.Parse(payload); }
        catch (JsonException) { throw new InvalidAuditEvent("invalid_event_json"); }
        using (json)
        {
            var root = json.RootElement;
            if (root.ValueKind != JsonValueKind.Object) throw new InvalidAuditEvent("invalid_event_shape");
            var names = root.EnumerateObject().Select(p => p.Name).ToArray();
            if (names.Distinct().Count() != names.Length) throw new InvalidAuditEvent("invalid_event_json");
            if (names.Length != Fields.Count || !Fields.SetEquals(names)) throw new InvalidAuditEvent("invalid_event_shape");
            var version = root.GetProperty("schemaVersion"); var type = root.GetProperty("type");
            if (version.ValueKind != JsonValueKind.Number || !version.TryGetInt32(out var number) || number != 1 ||
                type.ValueKind != JsonValueKind.String || type.GetString() != "TransferCompleted") throw new InvalidAuditEvent("unsupported_event_contract");
            Guid Identity(string name)
            {
                var value = root.GetProperty(name);
                if (value.ValueKind != JsonValueKind.String || !Guid.TryParseExact(value.GetString(), "D", out var id) || id == Guid.Empty)
                    throw new InvalidAuditEvent("invalid_event_identity");
                return id;
            }
            var source = Identity("sourceId"); var destination = Identity("destinationId");
            if (source == destination) throw new InvalidAuditEvent("invalid_event_identity");
            var amount = root.GetProperty("amountMinor"); var currency = root.GetProperty("currency");
            if (amount.ValueKind != JsonValueKind.Number || !amount.TryGetInt64(out var minor) || minor <= 0 || currency.ValueKind != JsonValueKind.String)
                throw new InvalidAuditEvent("invalid_event_money");
            try { _ = new Money(minor, currency.GetString()!); }
            catch (DomainException) { throw new InvalidAuditEvent("invalid_event_money"); }
            return new(Identity("eventId"), Identity("transferId"), source, destination, minor, currency.GetString()!);
        }
    }
}
